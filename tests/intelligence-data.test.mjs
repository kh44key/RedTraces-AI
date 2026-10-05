import test from 'node:test';
import assert from 'node:assert/strict';
import { makeDemo, emptyData, filterPeriod, countsBy, observableBundle } from '../app/intelligence-data.ts';

const now = new Date('2026-10-04T12:00:00Z');
test('demo totals are consistent across feed, sources and filtering', () => {
  const data = makeDemo(now);
  assert.equal(data.signals.length, 96);
  assert.equal(data.indicators.length, 32);
  assert.equal(new Set(data.signals.map(s => s.id)).size, 96);
  assert.equal(data.noise.accepted, data.signals.length);
  assert.equal(data.noise.processed, data.noise.accepted + data.noise.rejected);
  assert.equal(Object.values(data.noise.reasons).reduce((a,b)=>a+b,0), data.noise.rejected);
  assert.equal(countsBy(data.signals,s=>s.platform).reduce((n,[,count])=>n+count,0),96);
});
test('time filters use real record dates and exclude invalid and future dates', () => {
  const data = makeDemo(now);
  assert.equal(filterPeriod(data.signals,1,now.getTime()).length,18);
  assert.equal(filterPeriod(data.signals,7,now.getTime()).length,96);
  assert.equal(filterPeriod([{date:'invalid'},{date:'2027-01-01'}],7,now.getTime()).length,0);
  assert.ok(data.signals.every(s=>Date.parse(s.date)<now.getTime()));
});
test('live initial state never falls back to demo records', () => {
  const live=emptyData();
  assert.deepEqual(live.signals,[]);
  assert.deepEqual(live.indicators,[]);
  assert.equal(live.noise.processed,0);
  assert.equal(live.loaded,false);
});
test('sample indicators use documentation addresses and fictional domains', () => {
  for(const r of makeDemo(now).indicators){
    if(r.type==='IPv4') assert.match(r.value,/^203\.0\.113\./);
    if(r.type==='Domain') assert.ok(r.value.endsWith('.example'));
    if(r.type==='URL') assert.ok(new URL(r.value).hostname.endsWith('.example'));
    if(r.type==='SHA-256') assert.match(r.value,/^[0-9a-f]{64}$/);
  }
});
test('STIX export uses observables, valid IDs and an explicit demo marker', () => {
  const bundle=observableBundle(makeDemo(now).indicators,true);
  assert.equal(bundle.type,'bundle');
  assert.match(bundle.id,/^bundle--[0-9a-f-]{36}$/);
  assert.equal(bundle.x_redtraces_demo,true);
  assert.equal(bundle.objects.length,24);
  assert.ok(bundle.objects.every(o=>o.spec_version==='2.1'&&o.type!=='indicator'));
  assert.equal(new Set(bundle.objects.map(o=>o.id)).size,bundle.objects.length);
});
