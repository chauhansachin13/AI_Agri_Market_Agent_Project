import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';

import * as api from '../services/api.js';
import { useAuth } from '../context/AuthContext.jsx';

const CROPS = ['Tomato', 'Onion', 'Wheat', 'Potato', 'Rice', 'Maize', 'Mustard'];

const rupees = (value) =>
  `₹${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(value || 0)}`;

/** How the ask compares with the mandi rate recorded when the lot was listed. */
function AskVsMandi({ ask, reference }) {
  if (!reference) return null;
  const delta = ((ask - reference) / reference) * 100;
  const above = delta > 0;
  return (
    <span
      className="chip"
      style={{
        backgroundColor: above ? '#fef3c7' : '#dcfce7',
        color: above ? '#92400e' : '#166534',
      }}
      title={`Mandi rate when listed: ${rupees(reference)}`}
    >
      {above ? '▲' : '▼'} {Math.abs(delta).toFixed(0)}% vs mandi
    </span>
  );
}

function ListingCard({ listing, onSelect, index }) {
  return (
    <motion.article
      className="glass p-4"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.05, 0.3) }}
      data-testid="listing-card"
    >
      <header className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold">{listing.crop}</h3>
          <p className="text-xs opacity-60">
            {listing.location?.district}
            {listing.location?.state ? `, ${listing.location.state}` : ''} · {listing.grade}
          </p>
        </div>
        <span className="chip bg-mandi-100 text-mandi-800 dark:bg-white/10 dark:text-mandi-200">
          {listing.status}
        </span>
      </header>

      <p className="mt-3 text-xl font-bold text-mandi-700 dark:text-mandi-300">
        {rupees(listing.askPricePerQuintal)}
        <span className="ml-1 text-xs font-normal opacity-60">/ quintal</span>
      </p>
      <p className="text-sm opacity-70">{listing.quantityQuintal} quintal available</p>

      <div className="mt-2">
        <AskVsMandi ask={listing.askPricePerQuintal} reference={listing.mandiReferencePrice} />
      </div>

      {listing.notes && <p className="mt-2 text-xs opacity-70">{listing.notes}</p>}

      <button type="button" onClick={() => onSelect(listing)} className="btn-ghost mt-3 w-full text-sm">
        View offers · ऑफर देखें
      </button>
    </motion.article>
  );
}

export default function MarketplacePage() {
  const { user, isAuthenticated } = useAuth();
  const [listings, setListings] = useState([]);
  const [selected, setSelected] = useState(null);
  const [offers, setOffers] = useState([]);
  const [crop, setCrop] = useState('');
  const [district, setDistrict] = useState('');
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);
  const [form, setForm] = useState({
    crop: 'Wheat',
    quantityQuintal: '',
    askPricePerQuintal: '',
    notes: '',
  });
  const [bid, setBid] = useState('');

  const load = useCallback(async () => {
    setStatus('loading');
    setError(null);
    try {
      const data = await api.listListings({
        crop: crop || undefined,
        district: district || undefined,
      });
      setListings(data.listings || []);
      setStatus('ready');
    } catch (caught) {
      setError(caught.message);
      setStatus('error');
    }
  }, [crop, district]);

  useEffect(() => {
    load();
  }, [load]);

  const openListing = async (listing) => {
    try {
      const data = await api.getListing(listing._id);
      setSelected(data.listing);
      setOffers(data.offers || []);
    } catch (caught) {
      setError(caught.message);
    }
  };

  const submitListing = async (event) => {
    event.preventDefault();
    setError(null);
    try {
      await api.createListing({
        crop: form.crop,
        quantityQuintal: Number(form.quantityQuintal),
        askPricePerQuintal: Number(form.askPricePerQuintal),
        notes: form.notes || undefined,
      });
      setForm({ crop: 'Wheat', quantityQuintal: '', askPricePerQuintal: '', notes: '' });
      await load();
    } catch (caught) {
      setError(caught.message);
    }
  };

  const submitOffer = async (event) => {
    event.preventDefault();
    setError(null);
    try {
      await api.makeOffer(selected._id, { pricePerQuintal: Number(bid) });
      setBid('');
      await openListing(selected);
    } catch (caught) {
      setError(caught.message);
    }
  };

  const resolveOffer = async (offer, action) => {
    setError(null);
    try {
      if (action === 'accept') await api.acceptOffer(offer._id);
      else if (action === 'reject') await api.rejectOffer(offer._id);
      else await api.withdrawOffer(offer._id);
      await openListing(selected);
      await load();
    } catch (caught) {
      setError(caught.message);
    }
  };

  const isOwner = selected && user && String(selected.farmer) === String(user.id);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold">Farmer–Buyer Marketplace</h1>
        <p lang="hi" className="opacity-70">
          अपनी फसल सीधे खरीदार को बेचें
        </p>
      </header>

      {error && (
        <p className="glass mb-4 p-3 text-sm text-red-700 dark:text-red-300">{error}</p>
      )}

      <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="space-y-4">
          {isAuthenticated ? (
            <form onSubmit={submitListing} className="glass p-4">
              <h2 className="font-semibold">List your produce</h2>
              <p lang="hi" className="mb-3 text-xs opacity-60">
                अपनी फसल यहाँ डालें
              </p>

              <label className="block text-sm">
                <span className="mb-1 block opacity-70">Crop · फसल</span>
                <select
                  className="field"
                  value={form.crop}
                  onChange={(e) => setForm({ ...form, crop: e.target.value })}
                >
                  {CROPS.map((option) => (
                    <option key={option}>{option}</option>
                  ))}
                </select>
              </label>

              <label className="mt-3 block text-sm">
                <span className="mb-1 block opacity-70">Quantity (quintal) · मात्रा</span>
                <input
                  className="field"
                  type="number"
                  min="0.1"
                  step="0.1"
                  required
                  value={form.quantityQuintal}
                  onChange={(e) => setForm({ ...form, quantityQuintal: e.target.value })}
                />
              </label>

              <label className="mt-3 block text-sm">
                <span className="mb-1 block opacity-70">Asking price / quintal · भाव</span>
                <input
                  className="field"
                  type="number"
                  min="1"
                  required
                  value={form.askPricePerQuintal}
                  onChange={(e) => setForm({ ...form, askPricePerQuintal: e.target.value })}
                />
              </label>

              <label className="mt-3 block text-sm">
                <span className="mb-1 block opacity-70">Notes · जानकारी</span>
                <input
                  className="field"
                  maxLength={500}
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  placeholder="Grade, pickup, storage…"
                />
              </label>

              <button type="submit" className="btn-primary mt-4 w-full">
                List it · डालें
              </button>
            </form>
          ) : (
            <p className="glass p-4 text-sm opacity-70">
              Sign in to list your produce or make an offer.
              <span lang="hi" className="mt-1 block">
                फसल डालने या ऑफर देने के लिए लॉगिन करें।
              </span>
            </p>
          )}

          <div className="glass p-4">
            <h2 className="mb-3 font-semibold">Filter</h2>
            <label className="block text-sm">
              <span className="mb-1 block opacity-70">Crop</span>
              <select className="field" value={crop} onChange={(e) => setCrop(e.target.value)}>
                <option value="">All crops</option>
                {CROPS.map((option) => (
                  <option key={option}>{option}</option>
                ))}
              </select>
            </label>
            <label className="mt-3 block text-sm">
              <span className="mb-1 block opacity-70">District</span>
              <input
                className="field"
                value={district}
                onChange={(e) => setDistrict(e.target.value)}
                placeholder="All districts"
              />
            </label>
          </div>
        </aside>

        <main>
          {status === 'loading' && <p className="text-sm opacity-60">Loading…</p>}

          {status === 'ready' && listings.length === 0 && (
            <p className="glass p-6 text-center text-sm opacity-70">
              No produce listed yet for this filter.
              <span lang="hi" className="mt-1 block">
                अभी कोई फसल सूची में नहीं है।
              </span>
            </p>
          )}

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {listings.map((listing, index) => (
              <ListingCard
                key={listing._id}
                listing={listing}
                index={index}
                onSelect={openListing}
              />
            ))}
          </div>

          {selected && (
            <section className="glass mt-6 p-5" data-testid="listing-detail">
              <header className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-semibold">
                    {selected.crop} · {rupees(selected.askPricePerQuintal)}/qtl
                  </h2>
                  <p className="text-xs opacity-60">
                    {selected.quantityQuintal} quintal · {selected.location?.district} ·{' '}
                    {selected.status}
                  </p>
                </div>
                <button
                  type="button"
                  className="text-sm opacity-60 hover:opacity-100"
                  onClick={() => setSelected(null)}
                >
                  Close
                </button>
              </header>

              {isAuthenticated && !isOwner && selected.status === 'open' && (
                <form onSubmit={submitOffer} className="mt-4 flex gap-2">
                  <input
                    className="field"
                    type="number"
                    min="1"
                    required
                    placeholder="Your offer per quintal"
                    value={bid}
                    onChange={(e) => setBid(e.target.value)}
                  />
                  <button type="submit" className="btn-primary whitespace-nowrap">
                    Offer · ऑफर दें
                  </button>
                </form>
              )}

              <h3 className="mt-5 text-sm font-semibold uppercase tracking-wide opacity-60">
                Offers · ऑफर
              </h3>
              {offers.length === 0 ? (
                <p className="mt-2 text-sm opacity-60">No offers yet.</p>
              ) : (
                <ul className="mt-2 space-y-2">
                  {offers.map((offer) => (
                    <li
                      key={offer._id}
                      className="flex flex-wrap items-center gap-3 rounded-lg bg-black/5 p-3 text-sm dark:bg-white/5"
                    >
                      <span className="font-semibold">{rupees(offer.pricePerQuintal)}/qtl</span>
                      <span className="opacity-70">{offer.quantityQuintal} qtl</span>
                      <span className="chip bg-black/10 dark:bg-white/10">{offer.status}</span>
                      {offer.message && <span className="opacity-60">{offer.message}</span>}

                      {isOwner && offer.status === 'pending' && (
                        <span className="ml-auto flex gap-2">
                          <button
                            type="button"
                            className="btn-primary px-3 py-1 text-xs"
                            onClick={() => resolveOffer(offer, 'accept')}
                          >
                            Accept
                          </button>
                          <button
                            type="button"
                            className="btn-ghost px-3 py-1 text-xs"
                            onClick={() => resolveOffer(offer, 'reject')}
                          >
                            Reject
                          </button>
                        </span>
                      )}

                      {!isOwner &&
                        user &&
                        String(offer.buyer) === String(user.id) &&
                        offer.status === 'pending' && (
                          <button
                            type="button"
                            className="btn-ghost ml-auto px-3 py-1 text-xs"
                            onClick={() => resolveOffer(offer, 'withdraw')}
                          >
                            Withdraw
                          </button>
                        )}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
