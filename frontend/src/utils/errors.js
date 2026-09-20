/**
 * Standardized API Error abstraction and response normalization.
 */

export class ApiError extends Error {
  constructor(message, status = 500, code = 'INTERNAL_ERROR', details = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export async function parseApiResponse(response) {
  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }

  if (!response.ok) {
    const errorMsg = data?.detail || data?.message || data?.error || `HTTP ${response.status} Request Failed`;
    const errorCode = data?.error_code || (response.status === 401 ? 'UNAUTHORIZED' : response.status === 403 ? 'FORBIDDEN' : 'API_ERROR');
    throw new ApiError(errorMsg, response.status, errorCode, data);
  }

  return data;
}
