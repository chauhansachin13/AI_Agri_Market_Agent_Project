import ChatBot from '../components/ChatBot.jsx';
import MandiCard from '../components/MandiCard.jsx';
import ReasoningPanel from '../components/ReasoningPanel.jsx';
import { useQuery } from '../context/QueryContext.jsx';

export default function ChatPage() {
  const { latest } = useQuery();

  return (
    <div className="mx-auto grid max-w-7xl gap-6 px-4 py-8 lg:grid-cols-[minmax(0,1fr)_380px]">
      <div className="flex min-h-[70vh] flex-col">
        <ChatBot />
      </div>

      <div className="space-y-4">
        <ReasoningPanel response={latest} />

        {latest?.live_mandi_prices?.length > 0 && (
          <section>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide opacity-60">
              Prices used in this answer
            </h2>
            <div className="space-y-3">
              {latest.live_mandi_prices.slice(0, 4).map((record, index) => (
                <MandiCard
                  key={`${record.market}-${record.arrival_date}-${index}`}
                  record={record}
                  trend={latest.trend_analysis?.direction}
                  best={index === 0}
                  index={index}
                />
              ))}
            </div>
          </section>
        )}

        {latest?.buyers?.length > 0 && (
          <section className="glass p-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide opacity-60">
              Buyers · खरीदार
            </h2>
            <ul className="mt-3 space-y-3">
              {latest.buyers.slice(0, 5).map((buyer) => (
                <li key={buyer.apmc_name} className="text-sm">
                  <p className="font-medium">{buyer.apmc_name}</p>
                  <p className="text-xs opacity-70">{buyer.address}</p>
                  <p className="text-xs opacity-70">
                    {buyer.trading_hours}
                    {buyer.contact ? ` · ${buyer.contact}` : ''}
                  </p>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}
