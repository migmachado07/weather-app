import { api } from './api.js';
import { hoursForDay, rainSummary } from './hourly.js';

const $ = id => document.getElementById(id);
const number = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });
const state = { city: null, requestedCity: null, favorites: [], favoriteBusy: false,
  weather: null, selectedDay: null,
  weatherController: null, searchController: null, searchVersion: 0, results: [], active: -1 };
let searchTimer, toastTimer;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.classList.add('icon');
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `#i-${name}`);
  svg.append(use);
  return svg;
}

function condition(code, day = true) {
  if (code === 0) return [day ? 'Céu limpo' : 'Noite de céu limpo', day ? 'sun' : 'moon', day ? 'sunny' : 'night'];
  if (code <= 3) return [code === 3 ? 'Céu encoberto' : 'Parcialmente nublado', 'cloud', day ? 'cloudy' : 'night'];
  if ([45, 48].includes(code)) return ['Nevoeiro', 'cloud', day ? 'cloudy' : 'night'];
  if ([71, 73, 75, 77, 85, 86].includes(code)) return ['Neve', 'snow', day ? 'cloudy' : 'night'];
  if (code >= 95) return ['Trovoadas', 'storm', day ? 'rainy' : 'night'];
  return ['Chuva', 'rain', day ? 'rainy' : 'night'];
}

function toast(message) {
  $('toast').textContent = message;
  $('toast').hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, 4500);
}

function metric(id, value, unit) {
  $(id).replaceChildren(document.createTextNode(number.format(value)), element('small', '', unit));
}

function selectDay(date) {
  state.selectedDay = date;
  document.querySelectorAll('.forecast-day').forEach(button => {
    button.setAttribute('aria-pressed', String(button.dataset.date === date));
  });
  const data = state.weather;
  const today = date === data.today.date;
  const label = today ? 'Hoje' : new Date(`${date}T12:00:00`).toLocaleDateString('pt-BR',
    { weekday: 'long', day: '2-digit', month: 'short' });
  const hours = hoursForDay(data, date);
  $('hourly-title').textContent = `Hora a hora · ${label}`;
  $('hourly-summary').textContent = hours.length ? rainSummary(hours, data.current.time, today) :
    'A previsão por hora está indisponível para este dia. Os dados diários continuam acima.';
  $('hourly-timezone').textContent = `Horários de ${state.city.city_name} · ${data.timezone}`;
  $('hourly-scroll').replaceChildren(...hours.map(hour => {
    const card = element('li', 'hour-card');
    const currentHour = today && hour.time.slice(0, 13) === data.current.time.slice(0, 13);
    if (currentHour) { card.classList.add('current-hour'); card.setAttribute('aria-current', 'time'); }
    if (today && hour.time.slice(0, 13) < data.current.time.slice(0, 13)) card.classList.add('past-hour');
    if (hour.precipitation_probability >= 40) card.classList.add('rain-likely');
    const [description, symbol] = hour.weather_code == null ? ['Condição indisponível', 'clock'] :
      condition(hour.weather_code, hour.is_day !== false);
    const probability = hour.precipitation_probability == null ? '—' : `${Math.round(hour.precipitation_probability)}%`;
    card.append(element('span', 'hour-time', hour.time.slice(11, 16)),
      element('span', 'hour-now', currentHour ? 'Hora atual' : '\u00a0'), icon(symbol),
      element('span', 'hour-temp', hour.temperature == null ? '—' : `${Math.round(hour.temperature)}°`),
      element('span', 'hour-condition', description));
    const rain = element('span', 'hour-rain');
    rain.append(icon('drop'), document.createTextNode(probability));
    rain.setAttribute('aria-label', hour.precipitation_probability == null ? 'Chance de precipitação indisponível' :
      `${probability} de chance de precipitação na hora anterior`);
    card.append(rain, element('span', 'hour-volume', hour.precipitation == null ? 'Volume indisponível' :
      `${number.format(hour.precipitation)} mm`));
    return card;
  }));
  // Move somente a faixa horizontal, sem tirar o foco do dia escolhido.
  const track = $('hourly-scroll');
  const current = track.querySelector('.current-hour');
  track.scrollLeft = current ? current.offsetLeft - 6 : 0;
  $('hourly-previous').disabled = !hours.length;
  $('hourly-next').disabled = !hours.length;
}

for (const [id, direction] of [['hourly-previous', -1], ['hourly-next', 1]]) {
  $(id).addEventListener('click', () => $('hourly-scroll').scrollBy({
    left: direction * $('hourly-scroll').clientWidth * 0.75,
    behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
  }));
}

function renderWeather(payload, city) {
  const data = payload.weather_data;
  state.weather = data;
  const current = data.current;
  const [description, symbol, theme] = condition(current.weather_code, current.is_day);
  document.body.dataset.theme = theme;
  $('city-name').textContent = city.city_name;
  $('city-region').textContent = [city.state, city.country].filter(Boolean).join(', ') || `${city.lat.toFixed(2)}°, ${city.lon.toFixed(2)}°`;
  $('temperature').replaceChildren(document.createTextNode(Math.round(current.temperature)), element('small', '', '°C'));
  $('condition').textContent = description;
  $('hero-icon').replaceChildren(icon(symbol).firstElementChild);
  $('today-range').textContent = `↑ ${Math.round(data.today.temp_max)}°  ↓ ${Math.round(data.today.temp_min)}°`;
  $('current-time').textContent = `${current.time.slice(11, 16)} · hora local`;
  metric('feels-like', current.feels_like, '°C');
  metric('humidity', current.humidity, '%');
  metric('wind', current.wind_speed, 'km/h');
  metric('precipitation', current.precipitation, 'mm');
  $('ai-insight').textContent = payload.ai_insight;
  $('ai-badge').textContent = payload.ai_source === 'gemini' ? 'GEMINI AI' : 'DICA LOCAL · SEM IA';
  $('forecast-grid').replaceChildren(...[data.today, ...data.forecast].map((day, index) => {
    const [label, name] = condition(day.weather_code);
    const date = new Date(`${day.date}T12:00:00`);
    const card = element('button', 'forecast-day');
    card.type = 'button';
    card.dataset.date = day.date;
    card.setAttribute('aria-controls', 'hourly-panel');
    card.setAttribute('aria-pressed', 'false');
    card.addEventListener('click', () => selectDay(day.date));
    const temperatures = element('span', 'forecast-temp', `${Math.round(day.temp_max)}°`);
    temperatures.append(element('span', '', `${Math.round(day.temp_min)}°`));
    const rain = element('span', 'forecast-rain');
    rain.append(icon('drop'), document.createTextNode(`${Math.round(day.precipitation_probability)}%`));
    rain.title = 'Probabilidade máxima de precipitação no dia';
    card.append(element('span', 'forecast-name', index === 0 ? 'Hoje' : index === 1 ? 'Amanhã' : date.toLocaleDateString('pt-BR', { weekday: 'short' })),
      element('span', 'forecast-date', date.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })),
      icon(name), element('span', 'forecast-condition', label), temperatures, rain);
    return card;
  }));
  $('sunrise').textContent = data.today.sunrise?.slice(11, 16) || '—';
  $('sunset').textContent = data.today.sunset?.slice(11, 16) || '—';
  $('daylight-description').textContent = `Horários locais · ${data.timezone}`;
  const fetched = new Date(data.fetched_at).toLocaleTimeString('pt-BR', {
    hour: '2-digit', minute: '2-digit', timeZone: data.timezone,
  });
  $('data-status').textContent = `${payload.cached ? 'Em cache' : 'Atualizado'} às ${fetched} · ${data.timezone}`;
  updateFavoriteButton();
}

async function loadWeather(city, query = city.city_name) {
  state.weatherController?.abort();
  const controller = new AbortController();
  state.weatherController = controller;
  state.requestedCity = city;
  closeSearch();
  $('loading').hidden = false;
  $('dashboard').hidden = true;
  $('error-banner').hidden = true;
  $('main').setAttribute('aria-busy', 'true');
  try {
    const payload = await api.weather(city, query, controller.signal);
    if (controller !== state.weatherController) return;
    state.city = city;
    renderWeather(payload, city);
    $('dashboard').hidden = false;
    // As dimensões só existem depois de revelar o dashboard.
    selectDay(payload.weather_data.today.date);
    await refreshHistory();
  } catch (error) {
    if (controller !== state.weatherController || error.name === 'AbortError') return;
    $('error-message').textContent = error.message;
    $('error-banner').hidden = false;
  } finally {
    if (controller === state.weatherController) {
      $('loading').hidden = true;
      $('main').removeAttribute('aria-busy');
    }
  }
}

function closeSearch() {
  clearTimeout(searchTimer);
  state.searchVersion += 1;
  state.searchController?.abort();
  $('search-results').hidden = true;
  $('city-search').setAttribute('aria-expanded', 'false');
  $('city-search').removeAttribute('aria-activedescendant');
  state.active = -1;
}

function setActive(index) {
  if (!state.results.length) return;
  state.active = (index + state.results.length) % state.results.length;
  [...$('search-results').children].forEach((node, i) => node.setAttribute('aria-selected', String(i === state.active)));
  $('city-search').setAttribute('aria-activedescendant', `city-option-${state.active}`);
}

function selectCity(index) {
  const city = state.results[index];
  if (!city) return;
  const query = $('city-search').value.trim();
  $('city-search').value = city.city_name;
  $('search-status').textContent = '';
  loadWeather(city, query);
}

async function search(query) {
  state.searchController?.abort();
  const controller = new AbortController();
  state.searchController = controller;
  const version = ++state.searchVersion;
  $('search-status').textContent = 'Buscando cidades…';
  try {
    const cities = await api.search(query, controller.signal);
    if (version !== state.searchVersion) return;
    state.results = cities;
    state.active = -1;
    $('search-results').replaceChildren(...cities.map((city, index) => {
      const option = element('div', 'search-option', city.city_name);
      option.id = `city-option-${index}`;
      option.setAttribute('role', 'option');
      option.setAttribute('aria-selected', 'false');
      option.append(element('small', '', [city.state, city.country].filter(Boolean).join(' · ')));
      option.addEventListener('click', () => selectCity(index));
      return option;
    }));
    $('search-results').hidden = !cities.length;
    $('city-search').setAttribute('aria-expanded', String(Boolean(cities.length)));
    $('search-status').textContent = cities.length ? `${cities.length} cidades encontradas. Selecione uma opção.` : 'Nenhuma cidade encontrada. Tente outro nome.';
  } catch (error) {
    if (version === state.searchVersion && error.name !== 'AbortError') $('search-status').textContent = error.message;
  }
}

$('city-search').addEventListener('input', () => {
  closeSearch();
  const query = $('city-search').value.trim();
  $('search-status').textContent = query.length < 2 ? 'Digite pelo menos 2 caracteres.' : '';
  if (query.length >= 2) searchTimer = setTimeout(() => search(query), 300);
});
$('city-search').addEventListener('keydown', event => {
  if (event.key === 'Escape') closeSearch();
  if ($('search-results').hidden) return;
  if (['ArrowDown', 'ArrowUp'].includes(event.key)) {
    event.preventDefault();
    setActive(state.active + (event.key === 'ArrowDown' ? 1 : -1));
  }
  if (event.key === 'Enter') { event.preventDefault(); selectCity(Math.max(0, state.active)); }
  if (event.key === 'Tab') closeSearch();
});
document.addEventListener('click', event => { if (!event.target.closest('.search-wrap')) closeSearch(); });
document.addEventListener('keydown', event => {
  if (event.key === '/' && !event.ctrlKey && !event.metaKey && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
    event.preventDefault(); $('city-search').focus();
  }
});

function savedCity() {
  return state.city && state.favorites.find(city => Math.abs(city.lat - state.city.lat) < 0.0001 && Math.abs(city.lon - state.city.lon) < 0.0001);
}
function updateFavoriteButton() {
  const saved = Boolean(savedCity());
  $('favorite-button').setAttribute('aria-pressed', String(saved));
  $('favorite-button').setAttribute('aria-label', saved ? 'Remover dos favoritos' : 'Salvar nos favoritos');
  $('favorite-button').disabled = state.favoriteBusy;
}

function sidebarError(container, message, retry) {
  const button = element('button', 'empty-action', 'Tentar novamente');
  button.addEventListener('click', retry);
  container.replaceChildren(element('p', 'side-empty', message), button);
}

function renderFavorites() {
  $('favorites-count').textContent = state.favorites.length;
  $('favorites-list').replaceChildren(...state.favorites.map(city => {
    const row = element('div', 'city-item');
    const button = element('button', 'city-select');
    const name = element('span');
    name.append(element('strong', '', city.city_name), element('small', '', [city.state, city.country].filter(Boolean).join(', ')));
    button.append(icon('pin'), name);
    button.addEventListener('click', () => loadWeather(city));
    const remove = element('button', 'remove');
    remove.setAttribute('aria-label', `Remover ${city.city_name} dos favoritos`);
    remove.append(icon('close'));
    remove.disabled = state.favoriteBusy;
    remove.addEventListener('click', () => mutateFavorite(city));
    row.append(button, remove);
    return row;
  }));
  if (!state.favorites.length) $('favorites-list').append(element('p', 'side-empty', 'Suas cidades, sempre por perto. Toque na estrela para salvar.'));
  updateFavoriteButton();
}

async function refreshFavorites() {
  try { state.favorites = await api.favorites(); renderFavorites(); }
  catch { sidebarError($('favorites-list'), 'Não foi possível carregar os favoritos.', refreshFavorites); }
}

async function mutateFavorite(toRemove = null) {
  if (state.favoriteBusy || (!state.city && !toRemove)) return;
  state.favoriteBusy = true;
  renderFavorites();
  try {
    if (toRemove) {
      await api.remove(toRemove.id);
      state.favorites = state.favorites.filter(item => item.id !== toRemove.id);
      toast('Cidade removida dos favoritos.');
    } else {
      const saved = await api.save(state.city);
      if (!state.favorites.some(item => item.id === saved.id)) state.favorites.unshift(saved);
      toast('Cidade salva nos favoritos.');
    }
  } catch (error) { toast(error.message); }
  finally { state.favoriteBusy = false; renderFavorites(); }
}
$('favorite-button').addEventListener('click', () => mutateFavorite(savedCity()));

async function refreshHistory() {
  try {
    const history = await api.history();
    $('history-list').replaceChildren(...history.map(item => {
      const row = element('div', 'city-item');
      const button = element('button', 'city-select');
      const name = element('span');
      // O esquema de histórico não guarda coordenadas; o clique repete a
      // busca e permite desambiguar, em vez de abrir outra cidade por engano.
      name.append(element('strong', '', item.city_resolved), element('small', '',
        new Date(item.searched_at.endsWith('Z') || /[+-]\d\d:\d\d$/.test(item.searched_at)
          ? item.searched_at : `${item.searched_at}Z`).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })));
      button.append(icon('clock'), name);
      button.title = `Pesquisar novamente: ${item.query_term}`;
      button.addEventListener('click', () => {
        const coords = item.query_term.match(/^(-?\d+\.\d+),\s*(-?\d+\.\d+)$/);
        if (coords) {
          loadWeather({ city_name: 'Localização selecionada', state: '', country: '', lat: Number(coords[1]), lon: Number(coords[2]) }, item.query_term);
        } else {
          $('city-search').value = item.query_term;
          $('city-search').focus();
          search(item.query_term.slice(0, 150));
        }
      });
      row.append(button);
      return row;
    }));
    if (!history.length) $('history-list').append(element('p', 'side-empty', 'As cidades que você consultar aparecem aqui.'));
  } catch { sidebarError($('history-list'), 'Não foi possível carregar o histórico.', refreshHistory); }
}

$('retry-button').addEventListener('click', () => {
  if (state.requestedCity) loadWeather(state.requestedCity);
});
$('locate-button').addEventListener('click', () => {
  if (!navigator.geolocation) return toast('Seu navegador não oferece geolocalização. Pesquise uma cidade.');
  $('locate-button').disabled = true;
  navigator.geolocation.getCurrentPosition(position => {
    $('locate-button').disabled = false;
    const { latitude: lat, longitude: lon } = position.coords;
    loadWeather({ city_name: 'Minha localização', state: '', country: '', lat, lon }, `${lat.toFixed(4)}, ${lon.toFixed(4)}`);
  }, () => {
    $('locate-button').disabled = false;
    toast('Não foi possível acessar sua localização. Permita o acesso ou busque uma cidade.');
  }, { timeout: 10000, maximumAge: 300000 });
});

$('header-date').textContent = new Date().toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' });
refreshFavorites();
refreshHistory();
loadWeather({ city_name: 'São Paulo', state: 'São Paulo', country: 'Brasil', lat: -23.5505, lon: -46.6333 });
