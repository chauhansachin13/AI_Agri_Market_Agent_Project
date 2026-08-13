import { useCallback, useState } from 'react';

/**
 * Browser geolocation, used to seed the Location Resolution Agent.
 *
 * Position is requested only when the farmer asks for it — never on page load.
 * A refusal is a normal outcome, not an error state: the agent falls back to
 * pincode, IP and text extraction, so the UI must stay fully usable without it.
 */
export function useLocation() {
  const [coordinates, setCoordinates] = useState(null);
  const [status, setStatus] = useState('idle'); // idle | locating | ready | denied | unavailable
  const [error, setError] = useState(null);

  const supported = typeof navigator !== 'undefined' && 'geolocation' in navigator;

  const request = useCallback(() => {
    if (!supported) {
      setStatus('unavailable');
      setError('This browser cannot share your location.');
      return Promise.resolve(null);
    }

    setStatus('locating');
    setError(null);

    return new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const point = {
            latitude: Number(position.coords.latitude.toFixed(5)),
            longitude: Number(position.coords.longitude.toFixed(5)),
          };
          setCoordinates(point);
          setStatus('ready');
          resolve(point);
        },
        (caught) => {
          setStatus(caught.code === caught.PERMISSION_DENIED ? 'denied' : 'unavailable');
          setError(caught.message);
          resolve(null);
        },
        { enableHighAccuracy: false, timeout: 10000, maximumAge: 5 * 60 * 1000 },
      );
    });
  }, [supported]);

  const clear = useCallback(() => {
    setCoordinates(null);
    setStatus('idle');
    setError(null);
  }, []);

  return { supported, coordinates, status, error, request, clear };
}
