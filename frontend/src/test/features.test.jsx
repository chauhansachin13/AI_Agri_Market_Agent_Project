import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';

import ForecastChart from '../components/ForecastChart.jsx';
import WeatherCard from '../components/WeatherCard.jsx';

const history = [
  { date: '2026-08-01', modal_price: 2280 },
  { date: '2026-08-02', modal_price: 2290 },
  { date: '2026-08-03', modal_price: 2300 },
];

const forecast = {
  model_name: 'ridge-ar',
  points: [
    { horizon: 1, value: 2310, lower: 2260, upper: 2360 },
    { horizon: 7, value: 2380, lower: 2240, upper: 2520 },
  ],
  horizon_days: 7,
  expected_change_pct: 2.7,
  mape: 1.8,
  baseline_mape: 5.4,
  beats_baseline: true,
  trained_on: 90,
  confidence: 0.81,
  notes: [],
};

describe('ForecastChart', () => {
  test('renders the forecast with its crop heading', () => {
    render(<ForecastChart history={history} forecast={forecast} crop="Wheat" />);
    expect(screen.getByText('Wheat forecast')).toBeInTheDocument();
  });

  test('shows the expected change and horizon', () => {
    render(<ForecastChart history={history} forecast={forecast} crop="Wheat" />);
    expect(screen.getByTestId('forecast-change')).toHaveTextContent('2.7%');
    expect(screen.getByTestId('forecast-change')).toHaveTextContent('7 days');
  });

  test('names the model and how much data it was trained on', () => {
    render(<ForecastChart history={history} forecast={forecast} crop="Wheat" />);
    expect(screen.getByText(/ridge-ar model, trained on 90 days/)).toBeInTheDocument();
  });

  test('reports skill against the naive baseline', () => {
    render(<ForecastChart history={history} forecast={forecast} crop="Wheat" />);
    expect(screen.getByText(/better than the 5\.4% naive baseline/)).toBeInTheDocument();
  });

  test('says plainly when the model is no better than guessing', () => {
    // A model that loses to the baseline must not be presented as authoritative.
    const weak = { ...forecast, mape: 7.2, baseline_mape: 5.4, beats_baseline: false };
    render(<ForecastChart history={history} forecast={weak} crop="Wheat" />);
    expect(screen.getByText(/no better than a naive guess/)).toBeInTheDocument();
  });

  test('explains why the band widens', () => {
    render(<ForecastChart history={history} forecast={forecast} crop="Wheat" />);
    expect(screen.getByText(/the less certain it is/)).toBeInTheDocument();
  });

  test('renders an empty state without a forecast', () => {
    render(<ForecastChart history={history} forecast={null} />);
    expect(screen.getByTestId('forecast-empty')).toBeInTheDocument();
  });

  test('renders an empty state when the forecast has no points', () => {
    render(<ForecastChart history={history} forecast={{ ...forecast, points: [] }} />);
    expect(screen.getByTestId('forecast-empty')).toBeInTheDocument();
  });

  test('surfaces model notes', () => {
    const noted = { ...forecast, notes: ['only 9 observations'] };
    render(<ForecastChart history={history} forecast={noted} />);
    expect(screen.getByText(/only 9 observations/)).toBeInTheDocument();
  });
});

describe('WeatherCard', () => {
  const disruption = {
    district: 'Patna',
    state: 'Bihar',
    source: 'open-meteo',
    live: true,
    days: [],
    total_rain_mm: 120,
    heavy_rain_days: 2,
    heat_stress_days: 0,
    supply_risk: 'disruption',
    price_pressure: 'upward',
    confidence: 0.7,
    summary: 'Two days of heavy rain expected.',
    summary_hi: 'दो दिन तेज़ बारिश का अनुमान है।',
  };

  test('leads with the supply consequence, not the weather', () => {
    render(<WeatherCard weather={disruption} />);
    expect(screen.getByText(/Supply may be disrupted/)).toBeInTheDocument();
  });

  test('states the price implication', () => {
    render(<WeatherCard weather={disruption} />);
    expect(screen.getByText(/Prices may firm/)).toBeInTheDocument();
  });

  test('shows the rainfall figures', () => {
    render(<WeatherCard weather={disruption} />);
    expect(screen.getByText('120 mm')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  test('shows the Hindi summary by default', () => {
    render(<WeatherCard weather={disruption} />);
    expect(screen.getByText('दो दिन तेज़ बारिश का अनुमान है।')).toBeInTheDocument();
  });

  test('shows the English summary when English is selected', () => {
    render(<WeatherCard weather={disruption} language="en" />);
    expect(screen.getByText('Two days of heavy rain expected.')).toBeInTheDocument();
  });

  test('marks a modelled outlook as not being a live forecast', () => {
    render(<WeatherCard weather={{ ...disruption, live: false, source: 'climatology' }} />);
    expect(screen.getByText(/Seasonal model — no live forecast/)).toBeInTheDocument();
  });

  test('labels a live forecast with its source', () => {
    render(<WeatherCard weather={disruption} />);
    expect(screen.getByText(/Live forecast \(open-meteo\)/)).toBeInTheDocument();
  });

  test('renders a surplus outlook', () => {
    const surplus = {
      ...disruption,
      supply_risk: 'surplus',
      price_pressure: 'downward',
      summary_hi: 'गर्मी रहेगी।',
    };
    render(<WeatherCard weather={surplus} />);
    expect(screen.getByText(/Arrivals may increase/)).toBeInTheDocument();
    expect(screen.getByText(/Prices may soften/)).toBeInTheDocument();
  });

  test('renders nothing without a weather signal', () => {
    const { container } = render(<WeatherCard weather={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
