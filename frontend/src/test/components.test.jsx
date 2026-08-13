import { render, screen, within } from '@testing-library/react';
import { describe, expect, test } from 'vitest';

import ConfidenceBar from '../components/ConfidenceBar.jsx';
import MandiCard from '../components/MandiCard.jsx';
import ReasoningPanel from '../components/ReasoningPanel.jsx';
import TrendChart from '../components/TrendChart.jsx';

const record = {
  state: 'Bihar',
  district: 'Patna',
  market: 'Patna City',
  commodity: 'Wheat',
  variety: 'Other',
  grade: 'FAQ',
  arrival_date: new Date().toISOString().slice(0, 10),
  min_price: 2250,
  max_price: 2350,
  modal_price: 2300,
  price_range: 100,
  source: 'agmarknet',
};

const agentResponse = {
  intent: 'price_query',
  crop: 'Wheat',
  location: 'Patna, Bihar',
  live_mandi_prices: [record],
  buyers: [],
  best_mandi: 'Patna City, Patna',
  trend_analysis: {
    direction: 'upward',
    ema_7: 2350,
    ema_14: 2320,
    ema_30: 2300,
    volatility: 0.02,
    confidence: 0.7,
    samples: 30,
  },
  prediction: { recommendation: 'SELL', confidence: 0.72, reason: 'prices are near a local high' },
  confidence_score: 0.81,
  fact_check_status: 'verified',
  fact_check_claims: [
    {
      claim: 'Price of Rs 2300 per quintal',
      status: 'verified',
      evidence: ['Patna City, Patna on 2026-08-01'],
    },
  ],
  english_answer: 'Wheat is Rs 2300 per quintal.',
  hindi_answer: 'गेहूं का भाव 2300 रुपये प्रति क्विंटल है।',
  reasoning_steps: [
    'Intent Detection: classified as price_query',
    'Mandi Intelligence: 1 record fetched',
  ],
  retrieved_context: ['[agmarknet: Wheat / Patna City] modal Rs 2300'],
  search_snippets: [],
  elapsed_ms: 42,
  degraded: false,
};

describe('ConfidenceBar', () => {
  test('renders the score as a percentage', () => {
    render(<ConfidenceBar score={0.81} />);
    expect(screen.getByText('81%')).toBeInTheDocument();
  });

  test('labels a high score as high confidence', () => {
    render(<ConfidenceBar score={0.9} />);
    expect(screen.getByText('High')).toBeInTheDocument();
  });

  test('labels a low score as low confidence', () => {
    render(<ConfidenceBar score={0.2} />);
    expect(screen.getByText('Low')).toBeInTheDocument();
  });

  test('clamps a score above 1', () => {
    render(<ConfidenceBar score={4.2} />);
    expect(screen.getByText('100%')).toBeInTheDocument();
  });

  test('clamps a negative score', () => {
    render(<ConfidenceBar score={-1} />);
    expect(screen.getByText('0%')).toBeInTheDocument();
  });

  test('renders a compact variant', () => {
    render(<ConfidenceBar score={0.5} compact />);
    expect(screen.getByTestId('confidence-compact')).toBeInTheDocument();
  });
});

describe('MandiCard', () => {
  test('shows the market, district and modal price', () => {
    render(<MandiCard record={record} />);
    expect(screen.getByText('Patna City')).toBeInTheDocument();
    expect(screen.getByText('Patna, Bihar')).toBeInTheDocument();
    expect(screen.getByText('₹2,300')).toBeInTheDocument();
  });

  test('marks the best-price mandi', () => {
    render(<MandiCard record={record} best />);
    expect(screen.getByText(/Best price/)).toBeInTheDocument();
  });

  test('shows a trend marker when a direction is given', () => {
    render(<MandiCard record={record} trend="upward" />);
    expect(screen.getByText(/Rising/)).toBeInTheDocument();
  });

  test("flags a record that is several days old", () => {
    const stale = { ...record, arrival_date: '2020-01-01' };
    render(<MandiCard record={stale} />);
    expect(screen.getByText(/days old/)).toBeInTheDocument();
  });

  test('renders nothing without a record', () => {
    const { container } = render(<MandiCard record={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe('ReasoningPanel', () => {
  test('prompts the farmer before any question is asked', () => {
    render(<ReasoningPanel response={null} />);
    expect(screen.getByTestId('reasoning-panel-empty')).toBeInTheDocument();
  });

  test('renders every reasoning step', () => {
    render(<ReasoningPanel response={agentResponse} />);
    const steps = within(screen.getByTestId('reasoning-steps')).getAllByRole('listitem');
    expect(steps).toHaveLength(2);
    expect(screen.getByText(/classified as price_query/)).toBeInTheDocument();
  });

  test('shows the fact-check verdict', () => {
    render(<ReasoningPanel response={agentResponse} />);
    expect(screen.getAllByText('Verified against government data').length).toBeGreaterThan(0);
  });

  test('lists the fact-checked claims', () => {
    render(<ReasoningPanel response={agentResponse} />);
    expect(screen.getByText('Price of Rs 2300 per quintal')).toBeInTheDocument();
  });

  test('warns when the response used offline data', () => {
    render(<ReasoningPanel response={{ ...agentResponse, degraded: true }} />);
    expect(screen.getByText(/offline\s+reference dataset/)).toBeInTheDocument();
  });

  test('does not warn when the data was live', () => {
    render(<ReasoningPanel response={agentResponse} />);
    expect(screen.queryByText(/offline\s+reference dataset/)).not.toBeInTheDocument();
  });

  test('shows the retrieved historical context', () => {
    render(<ReasoningPanel response={agentResponse} />);
    expect(screen.getByText(/\[agmarknet: Wheat \/ Patna City\]/)).toBeInTheDocument();
  });
});

describe('TrendChart', () => {
  const points = [
    { date: '2026-07-30', modal_price: 2280 },
    { date: '2026-07-31', modal_price: 2290 },
    { date: '2026-08-01', modal_price: 2300 },
  ];

  test('renders the chart with a crop heading', () => {
    render(<TrendChart points={points} trend={agentResponse.trend_analysis} crop="Wheat" />);
    expect(screen.getByText('Wheat price trend')).toBeInTheDocument();
  });

  test('shows the sell recommendation overlay', () => {
    render(
      <TrendChart
        points={points}
        trend={agentResponse.trend_analysis}
        prediction={agentResponse.prediction}
        crop="Wheat"
      />,
    );
    expect(screen.getByText(/Sell now/)).toBeInTheDocument();
  });

  test('shows the three moving averages', () => {
    render(<TrendChart points={points} trend={agentResponse.trend_analysis} crop="Wheat" />);
    expect(screen.getByText(/7-day avg ₹2,350/)).toBeInTheDocument();
    expect(screen.getByText(/30-day avg ₹2,300/)).toBeInTheDocument();
  });

  test('handles an empty series', () => {
    render(<TrendChart points={[]} />);
    expect(screen.getByTestId('trend-chart-empty')).toBeInTheDocument();
  });
});
