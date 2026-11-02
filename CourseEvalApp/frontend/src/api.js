// Small wrapper around fetch for the backend API (served under <base>/api).
const API_BASE = `${import.meta.env.BASE_URL}api`;
const TOKEN_KEY = 'courseeval_token';

export const getToken = () => {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
};
export const setToken = (token) => {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch { /* storage unavailable: the user just signs in again */ }
};

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

const readError = async (response) => {
  try {
    const body = await response.json();
    if (typeof body.detail === 'string') return body.detail;
    if (Array.isArray(body.detail) && body.detail.length) {
      // FastAPI validation errors: show the first message in plain words
      return body.detail[0].msg?.replace(/^Value error, /, '') || 'Please check the form';
    }
  } catch { /* not JSON */ }
  return `Request failed (${response.status})`;
};

let onUnauthorized = () => {};
export const setUnauthorizedHandler = (handler) => { onUnauthorized = handler; };

export async function api(path, { method = 'GET', body, form, raw = false } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  const response = await fetch(`${API_BASE}${path}`, { method, headers, body: payload });
  if (response.status === 401 && token) {
    setToken(null);
    onUnauthorized();
  }
  if (!response.ok) throw new ApiError(response.status, await readError(response));
  if (raw || response.status === 204) return response;
  return response.json();
}

export const formatDate = (value) => {
  if (!value) return '—';
  const date = new Date(value.endsWith?.('Z') || value.includes?.('+') ? value : `${value}Z`);
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
};

export const formatMoney = (value) => (value === null || value === undefined ? '—' : `$${Number(value).toFixed(2)}`);
