/** Paging state (runes). Clamping/slicing lives in logic/paging.ts. */
export class PagingStore {
  page = $state(1);
  pageSize = $state(24);

  goTo(page: number): void {
    this.page = Math.max(1, Math.floor(page) || 1);
  }

  resetToFirst(): void {
    this.page = 1;
  }
}

export const paging = new PagingStore();
