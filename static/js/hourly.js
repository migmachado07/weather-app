// Horários ISO locais da cidade: não usar new Date(time), que aplicaria o fuso do visitante.
export function hoursForDay(data, date) {
  return (data.hourly || []).filter(hour => hour.time.slice(0, 10) === date)
    .sort((a, b) => a.time.localeCompare(b.time));
}

export function rainSummary(hours, currentTime, isToday) {
  const relevant = isToday ? hours.filter(hour => hour.time >= currentTime.slice(0, 13) + ':00') : hours;
  const known = relevant.filter(hour => hour.precipitation_probability != null);
  if (!known.length) return 'Probabilidade de chuva indisponível para estes horários.';
  const peak = Math.max(...known.map(hour => hour.precipitation_probability));
  const times = known.filter(hour => hour.precipitation_probability === peak)
    .map(hour => hour.time.slice(11, 16));
  const scope = isToday ? 'no restante do dia' : 'neste dia';
  const incomplete = known.length < relevant.length ? ' Há horários sem dados.' : '';
  if (peak === 0) return `A previsão indica 0% de chance de precipitação ${scope}.${incomplete}`;
  const when = times.length === known.length ? 'nos horários disponíveis' :
    `às ${times.slice(0, 3).join(', ')}${times.length > 3 ? ' e em outros horários' : ''}`;
  return `Maior chance ${scope}: ${Math.round(peak)}% ${when}.${incomplete}`;
}
