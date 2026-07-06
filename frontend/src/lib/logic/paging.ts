export interface PageResult<T> {
  items: T[];
  page: number;
  totalPages: number;
}

/**
 * Clamp `page` into [1, totalPages] and slice out that page.
 * `pageSize` <= 0 means "everything on one page".
 */
export function paginate<T>(
  data: readonly T[],
  page: number,
  pageSize: number
): PageResult<T> {
  if (pageSize <= 0) {
    return { items: [...data], page: 1, totalPages: 1 };
  }
  const totalPages = Math.max(1, Math.ceil(data.length / pageSize));
  const clamped = Math.min(Math.max(1, Math.floor(page) || 1), totalPages);
  const start = (clamped - 1) * pageSize;
  return {
    items: data.slice(start, start + pageSize),
    page: clamped,
    totalPages,
  };
}
