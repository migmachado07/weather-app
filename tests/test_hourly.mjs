import test from 'node:test';
import assert from 'node:assert/strict';
import { hoursForDay, rainSummary } from '../static/js/hourly.js';

test('separa dias pelo horário da cidade, sem conversão pelo fuso do navegador', () => {
  const data = { hourly: [
    {time:'2026-10-07T00:00'}, {time:'2026-10-06T23:00'}, {time:'2026-10-06T00:00'},
  ] };
  assert.deepEqual(hoursForDay(data, '2026-10-06').map(h => h.time), ['2026-10-06T00:00', '2026-10-06T23:00']);
});
test('pico de hoje ignora horas passadas e amanhã inclui o dia completo', () => {
  const hours = [
    {time:'2026-10-06T08:00', precipitation_probability:90},
    {time:'2026-10-06T16:00', precipitation_probability:60},
    {time:'2026-10-06T17:00', precipitation_probability:20},
  ];
  assert.match(rainSummary(hours, '2026-10-06T16:15', true), /60% às 16:00/);
  assert.match(rainSummary(hours, '2026-10-05T16:15', false), /90% às 08:00/);
});
test('ausência de probabilidade não é confundida com zero', () => {
  assert.match(rainSummary([{time:'2026-10-06T16:00', precipitation_probability:null}], '', false), /indisponível/);
  assert.match(rainSummary([{time:'2026-10-06T16:00', precipitation_probability:0}], '', false), /0%/);
  assert.deepEqual(hoursForDay({}, '2026-10-06'), []);
});
