import { beforeEach, describe, expect, it, vi } from "vitest";
import apiClient from "../lib/api";

global.fetch = vi.fn();

const mockJsonResponse = (data, ok = true, status = 200) => ({
  ok,
  status,
  statusText: ok ? "OK" : "Error",
  headers: new Headers({ "content-type": "application/json" }),
  json: async () => data,
});

describe("ApiClient", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    apiClient.setToken(null);
  });

  // ── Token Management ──────────────────────────────────────────────────────

  describe("Token Management", () => {
    it("setToken stores token in localStorage", () => {
      apiClient.setToken("abc123");
      expect(localStorage.getItem("access_token")).toBe("abc123");
      expect(apiClient.token).toBe("abc123");
    });

    it("setToken(null) removes token from localStorage", () => {
      apiClient.setToken("abc123");
      apiClient.setToken(null);
      expect(localStorage.getItem("access_token")).toBeNull();
      expect(apiClient.token).toBeNull();
    });

    it("includes Authorization header when token is set", async () => {
      apiClient.setToken("my-token");
      global.fetch.mockResolvedValueOnce(mockJsonResponse({ ok: true }));
      await apiClient.healthCheck();
      const [, config] = global.fetch.mock.calls[0];
      expect(config.headers.Authorization).toBe("Bearer my-token");
    });

    it("omits Authorization header when no token", async () => {
      global.fetch.mockResolvedValueOnce(mockJsonResponse({ ok: true }));
      await apiClient.healthCheck();
      const [, config] = global.fetch.mock.calls[0];
      expect(config.headers.Authorization).toBeUndefined();
    });
  });

  // ── Authentication ────────────────────────────────────────────────────────

  describe("Authentication", () => {
    it("login stores token on success", async () => {
      const mockData = {
        access_token: "login-tok",
        user: { id: 1, email: "a@b.com" },
      };
      global.fetch.mockResolvedValueOnce(mockJsonResponse(mockData));

      const result = await apiClient.login({
        email: "a@b.com",
        password: "pass",
      });

      expect(result).toEqual(mockData);
      expect(apiClient.token).toBe("login-tok");
      expect(localStorage.getItem("access_token")).toBe("login-tok");
    });

    it("login throws on 401", async () => {
      global.fetch.mockResolvedValueOnce(
        mockJsonResponse({ error: "Invalid credentials" }, false, 401),
      );
      await expect(
        apiClient.login({ email: "a@b.com", password: "bad" }),
      ).rejects.toThrow("Invalid credentials");
    });

    it("logout clears token even if API call fails", async () => {
      apiClient.setToken("tok");
      global.fetch.mockRejectedValueOnce(new Error("Network error"));
      await apiClient.logout();
      expect(apiClient.token).toBeNull();
    });

    it("refreshToken stores new access token", async () => {
      global.fetch.mockResolvedValueOnce(
        mockJsonResponse({ access_token: "refreshed-token" }),
      );
      await apiClient.refreshToken();
      expect(apiClient.token).toBe("refreshed-token");
      expect(localStorage.getItem("access_token")).toBe("refreshed-token");
    });

    it("register posts to /auth/register", async () => {
      const mockData = { access_token: "reg-tok", user: { id: 2 } };
      global.fetch.mockResolvedValueOnce(mockJsonResponse(mockData));

      await apiClient.register({
        email: "new@b.com",
        password: "pass",
        first_name: "A",
      });

      const [url] = global.fetch.mock.calls[0];
      expect(url).toContain("/auth/register");
    });

    it("setupMFA posts to /auth/mfa/setup", async () => {
      global.fetch.mockResolvedValueOnce(
        mockJsonResponse({ qr_code: "data:..." }),
      );
      await apiClient.setupMFA({ type: "totp" });
      const [url] = global.fetch.mock.calls[0];
      expect(url).toContain("/auth/mfa/setup");
    });

    it("verifyMFA posts to /auth/mfa/verify", async () => {
      global.fetch.mockResolvedValueOnce(mockJsonResponse({ verified: true }));
      await apiClient.verifyMFA({ code: "123456" });
      const [url] = global.fetch.mock.calls[0];
      expect(url).toContain("/auth/mfa/verify");
    });
  });

  // ── Error Handling ────────────────────────────────────────────────────────

  describe("Error Handling", () => {
    it("throws with server error message from JSON body", async () => {
      global.fetch.mockResolvedValueOnce(
        mockJsonResponse({ error: "Custom server error" }, false, 422),
      );
      await expect(apiClient.getUserProfile()).rejects.toThrow(
        "Custom server error",
      );
    });

    it("throws with HTTP status when no JSON body", async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        headers: new Headers({ "content-type": "text/html" }),
        json: async () => {
          throw new Error("not json");
        },
      });
      await expect(apiClient.getUserProfile()).rejects.toThrow("HTTP 500");
    });

    it("throws Request timeout on AbortError", async () => {
      global.fetch.mockRejectedValueOnce(
        Object.assign(new Error("aborted"), { name: "AbortError" }),
      );
      await expect(apiClient.getUserProfile()).rejects.toThrow(
        "Request timeout",
      );
    });

    it("serializes body object to JSON string", async () => {
      global.fetch.mockResolvedValueOnce(mockJsonResponse({ ok: true }));
      await apiClient.createAccount({
        account_code: "1000",
        account_name: "Cash",
      });
      const [, config] = global.fetch.mock.calls[0];
      expect(typeof config.body).toBe("string");
      const parsed = JSON.parse(config.body);
      expect(parsed.account_code).toBe("1000");
    });
  });

  // ── Ledger ────────────────────────────────────────────────────────────────

  describe("Ledger Operations", () => {
    it("getAccounts calls /accounts", async () => {
      const mockData = { accounts: [{ id: 1, account_name: "Cash" }] };
      global.fetch.mockResolvedValueOnce(mockJsonResponse(mockData));
      const result = await apiClient.getAccounts();
      expect(result).toEqual(mockData);
      const [url] = global.fetch.mock.calls[0];
      expect(url).toContain("/accounts");
    });

    it("getJournalEntries passes query params", async () => {
      global.fetch.mockResolvedValueOnce(
        mockJsonResponse({ journal_entries: [] }),
      );
      await apiClient.getJournalEntries({ per_page: 10, page: 2 });
      const [url] = global.fetch.mock.calls[0];
      expect(url).toContain("per_page=10");
      expect(url).toContain("page=2");
    });

    it("getTrialBalance includes as_of_date param", async () => {
      global.fetch.mockResolvedValueOnce(mockJsonResponse({}));
      await apiClient.getTrialBalance("2024-06-30");
      const [url] = global.fetch.mock.calls[0];
      expect(url).toContain("as_of_date=2024-06-30");
    });

    it("getTrialBalance works without date", async () => {
      global.fetch.mockResolvedValueOnce(mockJsonResponse({}));
      await apiClient.getTrialBalance();
      const [url] = global.fetch.mock.calls[0];
      expect(url).toContain("/reports/trial-balance");
      expect(url).not.toContain("as_of_date");
    });

    it("getIncomeStatement includes date range", async () => {
      global.fetch.mockResolvedValueOnce(mockJsonResponse({}));
      await apiClient.getIncomeStatement("2024-01-01", "2024-06-30");
      const [url] = global.fetch.mock.calls[0];
      expect(url).toContain("start_date=2024-01-01");
      expect(url).toContain("end_date=2024-06-30");
    });
  });

  // ── Payments ──────────────────────────────────────────────────────────────

  describe("Payment Operations", () => {
    it("getTransactions passes query params", async () => {
      global.fetch.mockResolvedValueOnce(
        mockJsonResponse({ transactions: [] }),
      );
      await apiClient.getTransactions({ per_page: 20 });
      const [url] = global.fetch.mock.calls[0];
      expect(url).toContain("per_page=20");
    });

    it("createTransaction posts to /transactions", async () => {
      global.fetch.mockResolvedValueOnce(
        mockJsonResponse({ transaction: { id: 1 } }),
      );
      await apiClient.createTransaction({ amount: 100, currency: "USD" });
      const [url, config] = global.fetch.mock.calls[0];
      expect(url).toContain("/transactions");
      expect(config.method).toBe("POST");
    });

    it("getExchangeRates includes base currency", async () => {
      global.fetch.mockResolvedValueOnce(mockJsonResponse({ rates: {} }));
      await apiClient.getExchangeRates("EUR");
      const [url] = global.fetch.mock.calls[0];
      expect(url).toContain("base=EUR");
    });

    it("getRecurringPayments calls correct endpoint", async () => {
      global.fetch.mockResolvedValueOnce(
        mockJsonResponse({ recurring_payments: [] }),
      );
      await apiClient.getRecurringPayments();
      const [url] = global.fetch.mock.calls[0];
      expect(url).toContain("/recurring-payments");
    });

    it("deletePaymentMethod sends DELETE request", async () => {
      global.fetch.mockResolvedValueOnce(mockJsonResponse({ deleted: true }));
      await apiClient.deletePaymentMethod("pm-123");
      const [url, config] = global.fetch.mock.calls[0];
      expect(url).toContain("/payment-methods/pm-123");
      expect(config.method).toBe("DELETE");
    });
  });

  // ── AI / Insights ─────────────────────────────────────────────────────────

  describe("AI Operations", () => {
    it("getInsights passes params", async () => {
      global.fetch.mockResolvedValueOnce(mockJsonResponse({ insights: [] }));
      await apiClient.getInsights({ per_page: 10 });
      const [url] = global.fetch.mock.calls[0];
      expect(url).toContain("/insights");
      expect(url).toContain("per_page=10");
    });

    it("markInsightRead posts to correct endpoint", async () => {
      global.fetch.mockResolvedValueOnce(mockJsonResponse({ updated: true }));
      await apiClient.markInsightRead("ins-42");
      const [url, config] = global.fetch.mock.calls[0];
      expect(url).toContain("/insights/ins-42/read");
      expect(config.method).toBe("POST");
    });

    it("sendChatMessage posts to session endpoint", async () => {
      global.fetch.mockResolvedValueOnce(
        mockJsonResponse({ message: { id: 1 } }),
      );
      await apiClient.sendChatMessage("sess-1", { content: "Hello" });
      const [url, config] = global.fetch.mock.calls[0];
      expect(url).toContain("/chat/sessions/sess-1/messages");
      expect(config.method).toBe("POST");
    });

    it("predictCashFlow posts data to predictions endpoint", async () => {
      global.fetch.mockResolvedValueOnce(
        mockJsonResponse({ prediction: 15000 }),
      );
      await apiClient.predictCashFlow({ months: 3 });
      const [url, config] = global.fetch.mock.calls[0];
      expect(url).toContain("/predictions/cash-flow");
      expect(config.method).toBe("POST");
    });
  });

  // ── Documents ─────────────────────────────────────────────────────────────

  describe("Document Operations", () => {
    it("getDocuments calls /documents", async () => {
      global.fetch.mockResolvedValueOnce(mockJsonResponse({ documents: [] }));
      await apiClient.getDocuments();
      const [url] = global.fetch.mock.calls[0];
      expect(url).toContain("/documents");
    });

    it("deleteDocument sends DELETE request", async () => {
      global.fetch.mockResolvedValueOnce(mockJsonResponse({ deleted: true }));
      await apiClient.deleteDocument("doc-99");
      const [url, config] = global.fetch.mock.calls[0];
      expect(url).toContain("/documents/doc-99");
      expect(config.method).toBe("DELETE");
    });

    it("shareDocument posts to share endpoint", async () => {
      global.fetch.mockResolvedValueOnce(mockJsonResponse({ shared: true }));
      await apiClient.shareDocument("doc-5", {
        email: "x@y.com",
        permission: "view",
      });
      const [url, config] = global.fetch.mock.calls[0];
      expect(url).toContain("/documents/doc-5/share");
      expect(config.method).toBe("POST");
    });
  });

  // ── Notifications ─────────────────────────────────────────────────────────

  describe("Notification Operations", () => {
    it("getNotifications calls user endpoint", async () => {
      global.fetch.mockResolvedValueOnce(
        mockJsonResponse({ notifications: [] }),
      );
      await apiClient.getNotifications("user-1");
      const [url] = global.fetch.mock.calls[0];
      expect(url).toContain("/notifications/user/user-1");
    });

    it("updateNotificationPreferences sends PUT", async () => {
      global.fetch.mockResolvedValueOnce(mockJsonResponse({ updated: true }));
      await apiClient.updateNotificationPreferences("user-1", { email: true });
      const [url, config] = global.fetch.mock.calls[0];
      expect(url).toContain("/notifications/preferences/user-1");
      expect(config.method).toBe("PUT");
    });
  });

  // ── Compliance ────────────────────────────────────────────────────────────

  describe("Compliance Operations", () => {
    it("getComplianceDashboard calls correct endpoint", async () => {
      global.fetch.mockResolvedValueOnce(mockJsonResponse({ stats: {} }));
      await apiClient.getComplianceDashboard();
      const [url] = global.fetch.mock.calls[0];
      expect(url).toContain("/compliance/dashboard");
    });

    it("performKYCVerification posts data", async () => {
      global.fetch.mockResolvedValueOnce(
        mockJsonResponse({ status: "pending" }),
      );
      await apiClient.performKYCVerification({ document_type: "passport" });
      const [url, config] = global.fetch.mock.calls[0];
      expect(url).toContain("/kyc/verify");
      expect(config.method).toBe("POST");
    });
  });

  // ── User Profile ──────────────────────────────────────────────────────────

  describe("User Profile", () => {
    it("getUserProfile calls /users/profile", async () => {
      global.fetch.mockResolvedValueOnce(mockJsonResponse({ user: { id: 1 } }));
      await apiClient.getUserProfile();
      const [url] = global.fetch.mock.calls[0];
      expect(url).toContain("/users/profile");
    });

    it("updateUserProfile sends PUT to /users/profile", async () => {
      global.fetch.mockResolvedValueOnce(mockJsonResponse({ user: { id: 1 } }));
      await apiClient.updateUserProfile({ first_name: "Updated" });
      const [url, config] = global.fetch.mock.calls[0];
      expect(url).toContain("/users/profile");
      expect(config.method).toBe("PUT");
    });
  });
});
