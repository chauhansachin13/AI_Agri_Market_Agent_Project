import { Link } from 'react-router-dom';

const SECTIONS = [
  {
    title: 'Product',
    links: [
      { to: '/chat', label: 'Ask the assistant' },
      { to: '/dashboard', label: 'Live mandi board' },
      { to: '/prices', label: 'Trends and forecast' },
      { to: '/market', label: 'Marketplace' },
    ],
  },
];

const SOURCES = [
  { href: 'https://agmarknet.gov.in/', label: 'Agmarknet' },
  { href: 'https://www.enam.gov.in/', label: 'eNAM' },
  { href: 'https://data.gov.in/', label: 'data.gov.in' },
];

export default function Footer() {
  return (
    <footer className="mt-auto border-t bg-[rgb(var(--surface-muted))]">
      <div className="container-page py-12">
        <div className="grid gap-10 md:grid-cols-[1.5fr_1fr_1fr]">
          <div>
            <p className="flex items-center gap-2 font-bold tracking-tight">
              <span aria-hidden="true">🌾</span> Agri Market AI
            </p>
            <p className="muted mt-3 max-w-sm text-sm leading-relaxed">
              Government-grounded mandi intelligence for Indian farmers, in seven languages,
              with every figure traceable to its source.
            </p>
            <p lang="hi" className="muted mt-2 max-w-sm text-sm">
              भाव सरकारी स्रोतों से। सौदा करने से पहले मंडी में भाव पक्का कर लें।
            </p>
          </div>

          {SECTIONS.map((section) => (
            <nav key={section.title} aria-label={section.title}>
              <p className="text-sm font-semibold">{section.title}</p>
              <ul className="mt-3 space-y-2">
                {section.links.map((link) => (
                  <li key={link.to}>
                    <Link to={link.to} className="muted text-sm hover:underline">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ))}

          <div>
            <p className="text-sm font-semibold">Data sources</p>
            <ul className="mt-3 space-y-2">
              {SOURCES.map((source) => (
                <li key={source.href}>
                  <a
                    href={source.href}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="muted text-sm hover:underline"
                  >
                    {source.label} ↗
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-10 flex flex-col gap-2 border-t pt-6 text-xs sm:flex-row sm:items-center sm:justify-between">
          <p className="muted">
            Price data belongs to the Government of India, published via Agmarknet and eNAM.
          </p>
          <p className="muted">
            Decision support, not financial advice. Confirm at the mandi before selling.
          </p>
        </div>
      </div>
    </footer>
  );
}
