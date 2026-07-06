import { DEFAULT_FILTERS, type FilterState } from "../logic/filters";

/** Filter state container (runes). Pure semantics live in logic/filters.ts. */
export class FiltersStore {
  state = $state<FilterState>({ ...DEFAULT_FILTERS });

  set(patch: Partial<FilterState>): void {
    Object.assign(this.state, patch);
  }

  reset(): void {
    Object.assign(this.state, DEFAULT_FILTERS);
  }
}

export const filters = new FiltersStore();
