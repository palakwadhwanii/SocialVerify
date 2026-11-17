import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { AuthProvider, ConversationVariant, Sender, ChatType } from "./enums";

export interface UserRecord {
  id: string;
  name: string | null;
  email: string;
  password: string | null;
  provider: AuthProvider;
  imageUrl: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ConversationRecord {
  id: string;
  userId: string;
  title: string;
  variant: ConversationVariant;
  createdAt: string;
  lastUpdated: string;
}

export interface ChatRecord {
  id: string;
  conversationId: string;
  sender: Sender;
  content: string;
  type: ChatType;
  createdAt: string;
}

interface DatabaseData {
  users: UserRecord[];
  conversations: ConversationRecord[];
  chats: ChatRecord[];
}

export class LocalStore {
  private dataDir: string;
  private filePath: string;
  private users: Map<string, UserRecord> = new Map();
  private conversations: Map<string, ConversationRecord> = new Map();
  private chats: Map<string, ChatRecord> = new Map();

  constructor() {
    this.dataDir = path.resolve(process.cwd(), "data");
    this.filePath = path.join(this.dataDir, "socialverify_db.json");
    this.load();
  }

  private load() {
    try {
      if (!fs.existsSync(this.dataDir)) {
        fs.mkdirSync(this.dataDir, { recursive: true });
      }
      if (fs.existsSync(this.filePath)) {
        const raw = fs.readFileSync(this.filePath, "utf-8");
        const parsed: DatabaseData = JSON.parse(raw);
        for (const u of parsed.users || []) this.users.set(u.id, u);
        for (const c of parsed.conversations || []) this.conversations.set(c.id, c);
        for (const ch of parsed.chats || []) this.chats.set(ch.id, ch);
      }
    } catch (err) {
      console.warn("[LocalStore] Warning loading local database file:", err);
    }
  }

  private persist() {
    try {
      if (!fs.existsSync(this.dataDir)) {
        fs.mkdirSync(this.dataDir, { recursive: true });
      }
      const data: DatabaseData = {
        users: Array.from(this.users.values()),
        conversations: Array.from(this.conversations.values()),
        chats: Array.from(this.chats.values()),
      };
      fs.writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");
    } catch (err) {
      console.error("[LocalStore] Failed to persist database:", err);
    }
  }

  // --- User Operations ---
  userWhere(filter: { email?: string; id?: string }) {
    return {
      first: async (): Promise<UserRecord | null> => {
        for (const user of this.users.values()) {
          if (filter.email && user.email.toLowerCase() === filter.email.toLowerCase()) return user;
          if (filter.id && user.id === filter.id) return user;
        }
        return null;
      },
      update: async (updates: Partial<UserRecord>): Promise<UserRecord | null> => {
        for (const user of this.users.values()) {
          if ((filter.email && user.email.toLowerCase() === filter.email.toLowerCase()) ||
              (filter.id && user.id === filter.id)) {
            const updated: UserRecord = {
              ...user,
              ...updates,
              updatedAt: new Date().toISOString(),
            };
            this.users.set(user.id, updated);
            this.persist();
            return updated;
          }
        }
        return null;
      }
    };
  }

  async createUser(data: {
    name?: string | null;
    email: string;
    password?: string | null;
    provider?: AuthProvider;
    imageUrl?: string | null;
  }): Promise<UserRecord> {
    const id = crypto.randomUUID().replace(/-/g, "").slice(0, 24);
    const now = new Date().toISOString();
    const user: UserRecord = {
      id,
      name: data.name ?? null,
      email: data.email,
      password: data.password ?? null,
      provider: data.provider ?? AuthProvider.CREDENTIALS,
      imageUrl: data.imageUrl ?? null,
      createdAt: now,
      updatedAt: now,
    };
    this.users.set(id, user);
    this.persist();
    return user;
  }

  // --- Conversation Operations ---
  conversationWhere(filter: { id?: string; userId?: string }) {
    let matches = Array.from(this.conversations.values()).filter((c) => {
      if (filter.id && c.id !== filter.id) return false;
      if (filter.userId && c.userId !== filter.userId) return false;
      return true;
    });

    let withChatsCount = false;

    const builder = {
      include: (_rel: string, _fn: any) => {
        withChatsCount = true;
        return builder;
      },
      orderBy: (_sortFn: any) => {
        matches.sort((a, b) => new Date(b.lastUpdated).getTime() - new Date(a.lastUpdated).getTime());
        return builder;
      },
      first: async (): Promise<ConversationRecord | null> => {
        return matches[0] || null;
      },
      all: async (): Promise<any[]> => {
        return matches.map((conv) => {
          if (withChatsCount) {
            const count = Array.from(this.chats.values()).filter((ch) => ch.conversationId === conv.id).length;
            return { ...conv, chats: count };
          }
          return conv;
        });
      },
      delete: async (): Promise<boolean> => {
        let deleted = false;
        for (const m of matches) {
          this.conversations.delete(m.id);
          // Delete chats in this conversation
          for (const [chatId, chat] of this.chats.entries()) {
            if (chat.conversationId === m.id) this.chats.delete(chatId);
          }
          deleted = true;
        }
        if (deleted) this.persist();
        return deleted;
      },
      update: async (updates: Partial<ConversationRecord>): Promise<ConversationRecord | null> => {
        if (matches.length === 0) return null;
        const target = matches[0];
        const updated: ConversationRecord = {
          ...target,
          ...updates,
          lastUpdated: updates.lastUpdated || new Date().toISOString(),
        };
        this.conversations.set(target.id, updated);
        this.persist();
        return updated;
      }
    };

    return builder;
  }

  async createConversation(data: {
    userId: string;
    title: string;
    variant: ConversationVariant;
  }): Promise<ConversationRecord> {
    const id = crypto.randomUUID();
    const now = new Date().toISOString();
    const conv: ConversationRecord = {
      id,
      userId: data.userId,
      title: data.title,
      variant: data.variant,
      createdAt: now,
      lastUpdated: now,
    };
    this.conversations.set(id, conv);
    this.persist();
    return conv;
  }

  // --- Chat Operations ---
  chatWhere(filter: { conversationId?: string }) {
    let matches = Array.from(this.chats.values()).filter((ch) => {
      if (filter.conversationId && ch.conversationId !== filter.conversationId) return false;
      return true;
    });

    const builder = {
      orderBy: (_sortFn: any) => {
        matches.sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime());
        return builder;
      },
      all: async (): Promise<ChatRecord[]> => {
        return matches;
      }
    };
    return builder;
  }

  async createChat(data: {
    conversationId: string;
    sender: Sender;
    content: string;
    type: ChatType;
  }): Promise<ChatRecord> {
    const id = crypto.randomUUID();
    const now = new Date().toISOString();
    const chat: ChatRecord = {
      id,
      conversationId: data.conversationId,
      sender: data.sender,
      content: data.content,
      type: data.type,
      createdAt: now,
    };
    this.chats.set(id, chat);
    this.persist();
    return chat;
  }
  getAllConversations(): ConversationRecord[] {
    this.load();
    return Array.from(this.conversations.values()).sort(
      (a, b) => new Date(b.lastUpdated).getTime() - new Date(a.lastUpdated).getTime()
    );
  }

  getAllChats(): ChatRecord[] {
    this.load();
    return Array.from(this.chats.values());
  }
}

export const localStore = new LocalStore();
