const BASE = '/api/v1';

async function request(path, options = {}) {
  const timeout = new AbortController();
  const relay = () => timeout.abort();
  options.signal?.addEventListener('abort', relay, { once: true });
  if (options.signal?.aborted) timeout.abort();
  const timer = setTimeout(() => timeout.abort(), 35000);
  try {
    const response = await fetch(`${BASE}${path}`, {
      ...options, signal: timeout.signal,
      headers: { 'Content-Type': 'application/json', ...options.headers },
    });
    if (!response.ok) {
      let body;
      try { body = await response.json(); } catch { body = {}; }
      throw new Error(typeof body.detail === 'string' ? body.detail :
        `Não foi possível concluir a solicitação (${response.status}).`);
    }
    return response.status === 204 ? null : await response.json();
  } catch (error) {
    if (error.name === 'AbortError' && !options.signal?.aborted) {
      throw new Error('A consulta demorou mais que o esperado. Tente novamente.');
    }
    if (error instanceof TypeError) throw new Error('Não foi possível conectar ao servidor. Verifique sua conexão.');
    throw error;
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener('abort', relay);
  }
}

export const api = {
  search: (q, signal) => request(`/search?${new URLSearchParams({ q })}`, { signal }),
  weather: (city, query, signal) => request(`/weather?${new URLSearchParams({
    lat: city.lat, lon: city.lon, city_name: city.city_name,
    state: city.state || '', country: city.country || '', query,
  })}`, { signal }),
  favorites: () => request('/favorites'),
  save: city => request('/favorites', { method: 'POST', body: JSON.stringify({
    city_name: city.city_name, state: city.state || '', country: city.country || '',
    lat: city.lat, lon: city.lon,
  }) }),
  remove: id => request(`/favorites/${id}`, { method: 'DELETE' }),
  history: () => request('/history'),
};
