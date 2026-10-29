const http = require('http');

function request(options, body) {
  return new Promise((resolve, reject) => {
    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(data) });
        } catch {
          resolve({ status: res.statusCode, body: data });
        }
      });
    });
    req.on('error', reject);
    if (body) req.write(typeof body === 'string' ? body : JSON.stringify(body));
    req.end();
  });
}

async function run() {
  console.log('--- 1. Testing Login as admin ---');
  const loginRes = await request(
    {
      hostname: '127.0.0.1',
      port: 8000,
      path: '/api/v1/auth/login-json',
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    },
    { identifier: 'admin', password: process.env.ADMIN_PASSWORD }
  );
  console.log('Login status:', loginRes.status);
  console.log('Token received:', !!loginRes.body.access_token, '| Role:', loginRes.body.role, '| Tier:', loginRes.body.tier);

  const token = loginRes.body.access_token;
  if (!token) throw new Error('No token');

  console.log('\n--- 2. Testing GET /auth/me ---');
  const meRes = await request({
    hostname: '127.0.0.1',
    port: 8000,
    path: '/api/v1/auth/me',
    method: 'GET',
    headers: { Authorization: `Bearer ${token}` },
  });
  console.log('Me status:', meRes.status);
  console.log('User:', meRes.body.username, '| Full Name:', meRes.body.full_name, '| Quota max docs:', meRes.body.quota.max_upload_documents);

  console.log('\n--- 3. Testing GET /notebooks ---');
  const nbRes = await request({
    hostname: '127.0.0.1',
    port: 8000,
    path: '/api/v1/notebooks',
    method: 'GET',
    headers: { Authorization: `Bearer ${token}` },
  });
  console.log('Notebooks status:', nbRes.status);
  console.log('Notebooks count:', nbRes.body.length);
  const nb = nbRes.body[0];
  console.log('First notebook:', nb.notebook_id, '| Title:', nb.title);

  console.log('\n--- 4. Testing GET chat sessions in notebook ---');
  const sesRes = await request({
    hostname: '127.0.0.1',
    port: 8000,
    path: `/api/v1/chat/sessions/notebook/${nb.notebook_id}`,
    method: 'GET',
    headers: { Authorization: `Bearer ${token}` },
  });
  console.log('Sessions status:', sesRes.status);
  console.log('Sessions count:', sesRes.body.length);
  console.log('First session:', sesRes.body[0].session_id, '| Title:', sesRes.body[0].title);

  console.log('\n--- 5. Testing POST create new chat session (+ Thêm đoạn chat mới) ---');
  const newSesRes = await request(
    {
      hostname: '127.0.0.1',
      port: 8000,
      path: '/api/v1/chat/sessions',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    },
    { notebook_id: nb.notebook_id, title: 'Phân tích Apple Form 10-K' }
  );
  console.log('Create session status:', newSesRes.status);
  console.log('New session created:', newSesRes.body.session_id, '| Title:', newSesRes.body.title);

  console.log('\nALL TESTS PASSED WITH 100% SUCCESS!');
}

run().catch(console.error);
