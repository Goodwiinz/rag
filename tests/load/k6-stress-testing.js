/*
 * Multimodal Enterprise RAG System — K6 Maximum Stress Test (shared dev)
 *
 * Ramps to 400 virtual users against the CURRENT backend + Supabase contracts
 * to locate the practical breaking point of shared dev. Intentionally
 * disruptive: drive it only via tests/load/run-shared-dev-max.sh, which layers
 * on Kubernetes monitoring, a rolling catastrophic-abort, and result capture.
 *
 * Auth model: Supabase owns identity. setup() mints confirmed test users with
 * the service-role key, exchanges a password grant for each user's access
 * token (a Supabase JWT), and RETURNS them — the only channel that crosses the
 * k6 setup->VU VM boundary (module-level state does NOT). The backend validates
 * the JWT and JIT-provisions a User+Organization on first call, so the tokens
 * work for search/list/profile/upload with no backend registration route.
 *
 * Cleanup: test users are freshly minted, so every document they own belongs to
 * this run. teardown() lists each user's documents and deletes them (cascade),
 * then deletes the Supabase identities. Uploads are also tagged with the run id
 * for attribution. Secrets, tokens and response bodies are never logged.
 *
 * Required env: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY.
 * Optional env: BASE_URL, RUN_ID, RESULTS_DIR, SETUP_USERS, PREFLIGHT=1.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter } from 'k6/metrics';
import { randomItem, randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.1.0/index.js';

// ---- Config (Supabase secrets are read but never logged) -------------------
const SUPABASE_URL = __ENV.SUPABASE_URL;
const SUPABASE_ANON_KEY = __ENV.SUPABASE_ANON_KEY;
const SUPABASE_SERVICE_ROLE_KEY = __ENV.SUPABASE_SERVICE_ROLE_KEY;

const BASE_URL = __ENV.BASE_URL || 'https://dev-api.gen-text.app';
const RUN_ID = __ENV.RUN_ID || `local-${Date.now()}`;
const RESULTS_DIR = __ENV.RESULTS_DIR || '/results';
const PREFLIGHT = __ENV.PREFLIGHT === '1';
const NUM_USERS = PREFLIGHT ? 1 : parseInt(__ENV.SETUP_USERS || '50', 10);

// Full-literal route constants: single source of route truth, and lets the
// python contract guard (test_k6_stress_contract.py) grep exact paths.
const ROUTES = {
  supabaseAdminUsers: `${SUPABASE_URL}/auth/v1/admin/users`,
  supabaseToken: `${SUPABASE_URL}/auth/v1/token?grant_type=password`,
  search: `${BASE_URL}/api/v1/search/`,
  documents: `${BASE_URL}/api/v1/documents`,
  me: `${BASE_URL}/api/v1/auth/me`,
  upload: `${BASE_URL}/api/v1/files/upload`,
};

const SEARCH_QUERIES = [
  'machine learning', 'artificial intelligence', 'data science',
  'neural networks', 'deep learning', 'natural language processing',
  'computer vision', 'algorithms', 'transformer models', 'AI research',
];
// vector-only search was Qdrant-backed and now returns 400 (Qdrant removed) —
// use only hybrid + fulltext.
const SEARCH_TYPES = ['hybrid', 'fulltext'];

const FULL_STAGES = [
  { duration: '2m', target: 20 },   // warm-up
  { duration: '5m', target: 50 },   // moderate
  { duration: '5m', target: 100 },  // high
  { duration: '10m', target: 200 }, // stress
  { duration: '5m', target: 300 },  // extreme
  { duration: '5m', target: 400 },  // breaking-point attempt
  { duration: '2m', target: 0 },    // cooldown
];

// http_req_failed abort is a COARSE backstop only: k6 evaluates thresholds
// against the CUMULATIVE metric, not a rolling 60s window — it fires when the
// run-wide failure rate exceeds 50% after the first 60s and cannot un-fire once
// tripped. The real rolling "50% for 60s" abort is the external monitor in
// run-shared-dev-max.sh, which SIGINTs k6 on sustained failure or pod restart.
const BASE_THRESHOLDS = {
  http_req_duration: ['p(95)<5000'],
  http_req_failed: [{ threshold: 'rate<0.5', abortOnFail: true, delayAbortEval: '60s' }],
};

// Generous setup/teardown windows: setup mints + authenticates up to
// SETUP_USERS identities (2 calls each) and teardown deletes every document
// they created plus the identities — both far exceed k6's 60s defaults at the
// 50-user max profile, and a killed teardown would strand data on shared dev.
const LIFECYCLE = { setupTimeout: '300s', teardownTimeout: '900s' };

export const options = PREFLIGHT
  ? { vus: 1, iterations: 4, thresholds: BASE_THRESHOLDS, insecureSkipTLSVerify: true, ...LIFECYCLE }
  : { stages: FULL_STAGES, thresholds: BASE_THRESHOLDS, insecureSkipTLSVerify: true, ...LIFECYCLE };

const uploadsCreated = new Counter('uploads_created');

// ---- Setup: mint + authenticate test identities ----------------------------
export function setup() {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY || !SUPABASE_SERVICE_ROLE_KEY) {
    throw new Error(
      'Missing required env: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY'
    );
  }
  const adminHeaders = {
    'Content-Type': 'application/json',
    apikey: SUPABASE_SERVICE_ROLE_KEY,
    Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
  };
  const users = [];
  for (let i = 0; i < NUM_USERS; i++) {
    const email = `stress-${RUN_ID}-${i}@example.com`;
    const password = `Stress!${RUN_ID}-${i}`;

    const created = http.post(
      ROUTES.supabaseAdminUsers,
      JSON.stringify({ email, password, email_confirm: true }),
      { headers: adminHeaders }
    );
    if (created.status !== 200 && created.status !== 201) continue;

    let userId;
    try { userId = JSON.parse(created.body).id; } catch (e) { continue; }
    if (!userId) continue;

    const tokenRes = http.post(
      ROUTES.supabaseToken,
      JSON.stringify({ email, password }),
      { headers: { 'Content-Type': 'application/json', apikey: SUPABASE_ANON_KEY } }
    );
    let token;
    if (tokenRes.status === 200) {
      try { token = JSON.parse(tokenRes.body).access_token; } catch (e) { token = null; }
    }
    if (token) {
      users.push({ id: userId, email, token });
    } else {
      // Compensating delete: never leak a created-but-unauthenticated identity.
      // teardown only knows the users setup() returns, so an orphan here would
      // survive the run. (Supabase rate-limits rapid password grants — the
      // sleep below keeps that failure rate low.)
      http.del(`${ROUTES.supabaseAdminUsers}/${userId}`, null, { headers: adminHeaders });
    }
    sleep(0.1);
  }

  if (users.length === 0) {
    // Fail loudly so a zero-load run can never masquerade as a successful one.
    throw new Error('setup authenticated 0 users — aborting');
  }
  console.log(`setup: ${users.length}/${NUM_USERS} identities ready (run ${RUN_ID})`);
  return { runId: RUN_ID, users, documentIds: [] };
}

// ---- VU iteration ----------------------------------------------------------
export default function (data) {
  const user = PREFLIGHT ? data.users[0] : randomItem(data.users);
  const authHeaders = { Authorization: `Bearer ${user.token}` };

  // Preflight: deterministically exercise all four op classes (1 VU × 4 iters).
  // Full run: approved 60/20/15/5 mix.
  let op;
  if (PREFLIGHT) {
    op = __ITER % 4;
  } else {
    const r = Math.random();
    op = r < 0.6 ? 0 : r < 0.8 ? 1 : r < 0.95 ? 2 : 3;
  }

  if (op === 0) doSearch(authHeaders);
  else if (op === 1) doDocumentList(authHeaders);
  else if (op === 2) doProfile(authHeaders);
  else doUpload(authHeaders);

  sleep(randomIntBetween(1, 3) / 10); // 0.1–0.3s think time
}

function doSearch(authHeaders) {
  const body = JSON.stringify({
    query: randomItem(SEARCH_QUERIES),
    search_type: randomItem(SEARCH_TYPES),
    limit: randomIntBetween(5, 15),
  });
  const res = http.post(ROUTES.search, body, {
    headers: { ...authHeaders, 'Content-Type': 'application/json' },
    tags: { name: 'search' },
    timeout: '30s',
  });
  check(res, { 'search 200': (r) => r.status === 200 });
}

function doDocumentList(authHeaders) {
  const res = http.get(`${ROUTES.documents}?page=${randomIntBetween(1, 5)}&size=20`, {
    headers: authHeaders,
    tags: { name: 'documents' },
    timeout: '15s',
  });
  check(res, { 'documents 200': (r) => r.status === 200 });
}

function doProfile(authHeaders) {
  const res = http.get(ROUTES.me, {
    headers: authHeaders,
    tags: { name: 'profile' },
    timeout: '15s',
  });
  check(res, { 'profile 200': (r) => r.status === 200 });
}

function doUpload(authHeaders) {
  const content = `stress ${RUN_ID} ${Date.now()} `.repeat(20);
  const payload = {
    // multipart: do NOT set Content-Type — k6 sets it with the boundary.
    file: http.file(content, `stress-${RUN_ID}-${__VU}-${__ITER}.txt`, 'text/plain'),
    title: `stress ${RUN_ID} ${__VU}-${__ITER}`,
    tags: JSON.stringify(['stress-test', RUN_ID]),
    custom_metadata: JSON.stringify({ run_id: RUN_ID }),
  };
  const res = http.post(ROUTES.upload, payload, {
    headers: authHeaders,
    tags: { name: 'upload' },
    timeout: '60s',
  });
  const ok = check(res, { 'upload 200/201': (r) => r.status === 200 || r.status === 201 });
  if (ok) uploadsCreated.add(1);
}

// ---- Teardown: run-scoped cleanup ------------------------------------------
export function teardown(data) {
  const adminHeaders = {
    apikey: SUPABASE_SERVICE_ROLE_KEY,
    Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
  };
  let deletedDocs = 0, residualDocs = 0, deletedUsers = 0, residualUsers = 0;

  for (const user of data.users) {
    const authHeaders = { Authorization: `Bearer ${user.token}` };
    // Fresh users → every document they own was created by this run.
    for (let page = 1; page <= 50; page++) {
      const res = http.get(`${ROUTES.documents}?page=${page}&size=100`, { headers: authHeaders });
      if (res.status !== 200) break;
      let docs = [];
      try { docs = JSON.parse(res.body).documents || []; } catch (e) { break; }
      if (docs.length === 0) break;
      for (const doc of docs) {
        if (!doc.id) continue;
        const del = http.del(`${ROUTES.documents}/${doc.id}?cascade=true`, null, { headers: authHeaders });
        if (del.status === 200 || del.status === 204) deletedDocs++;
        else residualDocs++;
      }
    }
    const delUser = http.del(`${ROUTES.supabaseAdminUsers}/${user.id}`, null, { headers: adminHeaders });
    if (delUser.status === 200 || delUser.status === 204) deletedUsers++;
    else residualUsers++;
  }
  console.log(
    `teardown run=${data.runId}: docs deleted=${deletedDocs} residual=${residualDocs}; ` +
    `users deleted=${deletedUsers} residual=${residualUsers}`
  );
}

// Machine-readable summary for post-run analysis (written into the mounted
// results dir; stdout kept terse to avoid dumping response data).
export function handleSummary(data) {
  return {
    [`${RESULTS_DIR}/summary.json`]: JSON.stringify(data, null, 2),
    stdout: `\nStress run ${RUN_ID} complete — summary at ${RESULTS_DIR}/summary.json\n`,
  };
}
