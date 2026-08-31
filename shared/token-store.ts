import type { WhoopTokens } from "./types.js";

export interface TokenStore {
  getWhoopTokens(): Promise<WhoopTokens | null>;
  setWhoopTokens(tokens: WhoopTokens): Promise<void>;
}

const KV_KEY = "whoop_tokens";

/** Used inside the Cloudflare Worker, which has a direct KV binding. */
export class WorkerKVTokenStore implements TokenStore {
  constructor(private kv: KVNamespace) {}

  async getWhoopTokens(): Promise<WhoopTokens | null> {
    return this.kv.get<WhoopTokens>(KV_KEY, "json");
  }

  async setWhoopTokens(tokens: WhoopTokens): Promise<void> {
    await this.kv.put(KV_KEY, JSON.stringify(tokens));
  }
}
