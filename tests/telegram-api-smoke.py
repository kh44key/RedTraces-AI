"""Exercise the running Telegram API and remove all temporary test records."""
import uuid
import httpx
import mysql.connector
from pkcert_config import mysql_config

handle = 'hexsentrytest_' + uuid.uuid4().hex[:12]
client = httpx.Client(base_url='http://127.0.0.1:8000', timeout=15)
conn = mysql.connector.connect(**mysql_config('telegram_leaks_db'))
try:
    account = client.get('/accounts').json()[0]
    assert account['active'] is False, 'Smoke test expects local-only mode'
    assert client.post('/add-channel', json={'link': '@'}).status_code == 422
    assert client.post('/add-channel', json={'link': 'https://t.me/+testinvite'}).status_code == 409
    for _ in range(2):
        r = client.post('/add-channel', json={'link': '@' + handle})
        assert r.status_code == 200, r.text
    assert len([x for x in client.get('/channels').json() if x['handle'] == handle]) == 1
    cursor = conn.cursor()
    cursor.execute('INSERT INTO leaks (channel,message_id,detected_domains,detected_entities,text,message_date,processed_at) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                   (handle,1,'["example.invalid"]','["test"]','Test signal '+handle,'2026-09-23T00:00:00Z','2026-09-23T00:00:00Z'))
    conn.commit()
    found = client.get('/search-leaks', params={'keyword':handle}).json()
    assert len(found) == 1 and found[0]['channel'] == handle
    assert found[0]['detected_domains'] == ['example.invalid']
    assert found[0]['severity'] == 'unknown'
    r = client.get('/leaks?limit=1', headers={'Origin':'http://localhost:3000'})
    assert r.status_code == 200 and r.headers['access-control-allow-origin'] == 'http://localhost:3000'
    assert client.delete('/remove-channel', params={'username':handle}).status_code == 200
    assert not any(x['handle'] == handle for x in client.get('/channels').json())
    print('PASS: offline startup, channel validation/deduplication/removal, search, JSON decoding and dashboard CORS')
finally:
    cursor = conn.cursor()
    cursor.execute('DELETE FROM leaks WHERE channel = %s', (handle,))
    cursor.execute('DELETE FROM watched_channels WHERE handle = %s', (handle,))
    conn.commit()
    cursor.close()
    conn.close()
    client.close()
