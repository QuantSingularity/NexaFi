import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import mobileApiClient from "../lib/mobileApi";

global.fetch = vi.fn();

describe("MobileApiClient", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mobileApiClient.token = null;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("Authentication", () => {
    it("sets token after successful login", async () => {
      const mockResponse = {
        token: "test-token",
        user: { id: 1, email: "test@example.com" },
      };

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await mobileApiClient.login({
        email: "test@example.com",
        password: "password",
      });

      expect(result).toEqual(mockResponse);
      expect(localStorage.setItem).toHaveBeenCalledWith(
        "access_token",
        "test-token",
      );
    });

    it("stores access_token when the API returns it instead of token", async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ access_token: "alt-token" }),
      });

      await mobileApiClient.login({ email: "a@b.com", password: "pw" });

      expect(localStorage.setItem).toHaveBeenCalledWith(
        "access_token",
        "alt-token",
      );
      expect(mobileApiClient.token).toBe("alt-token");
    });

    it("includes auth token in subsequent requests", async () => {
      mobileApiClient.token = "test-token";

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: "test" }),
      });

      await mobileApiClient.getProfile();

      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: "Bearer test-token",
          }),
        }),
      );
    });

    it("clears token on logout", async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await mobileApiClient.logout();

      expect(localStorage.removeItem).toHaveBeenCalledWith("access_token");
      expect(mobileApiClient.token).toBeNull();
    });
  });

  describe("Error Handling", () => {
    it("handles 401 unauthorized errors by throwing", async () => {
      // Mock window.location
      const originalLocation = window.location;
      delete window.location;
      window.location = { href: "" };

      fetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
      });

      await expect(mobileApiClient.getProfile()).rejects.toThrow(
        "Unauthorized",
      );
      expect(localStorage.removeItem).toHaveBeenCalledWith("access_token");

      window.location = originalLocation;
    });

    it("does not redirect or clear the session when login credentials are rejected", async () => {
      const originalLocation = window.location;
      delete window.location;
      window.location = { href: "" };
      mobileApiClient.token = "existing-token";

      fetch.mockResolvedValueOnce({ ok: false, status: 401 });

      await expect(
        mobileApiClient.login({ email: "a@b.com", password: "wrong" }),
      ).rejects.toThrow("Invalid email or password");
      expect(window.location.href).toBe("");
      expect(localStorage.removeItem).not.toHaveBeenCalled();

      window.location = originalLocation;
    });

    it("handles network errors", async () => {
      fetch.mockRejectedValueOnce(new Error("Network error"));

      await expect(mobileApiClient.getDashboardData()).rejects.toThrow(
        "Network error",
      );
    });

    it("handles 500 server errors", async () => {
      fetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      await expect(mobileApiClient.getProfile()).rejects.toThrow(/HTTP error/);
    });
  });

  describe("Caching", () => {
    it("sets cached data in localStorage", () => {
      const testData = { test: "data" };
      mobileApiClient.setCachedData("testKey", testData);

      expect(localStorage.setItem).toHaveBeenCalledWith(
        "cache_testKey",
        JSON.stringify(testData),
      );
    });

    it("gets cached data from localStorage", () => {
      const testData = { test: "data" };
      localStorage.getItem.mockReturnValue(JSON.stringify(testData));

      const result = mobileApiClient.getCachedData("testKey");

      expect(result).toEqual(testData);
      expect(localStorage.getItem).toHaveBeenCalledWith("cache_testKey");
    });

    it("returns null for missing cached data", () => {
      localStorage.getItem.mockReturnValue(null);

      const result = mobileApiClient.getCachedData("missingKey");

      expect(result).toBeNull();
    });

    it("clears all cached data", () => {
      const originalKeys = Object.keys;
      Object.keys = vi.fn(() => [
        "cache_key1",
        "cache_key2",
        "other_key",
        "token",
      ]);

      try {
        mobileApiClient.clearCache();

        expect(localStorage.removeItem).toHaveBeenCalledWith("cache_key1");
        expect(localStorage.removeItem).toHaveBeenCalledWith("cache_key2");
        expect(localStorage.removeItem).not.toHaveBeenCalledWith("other_key");
        expect(localStorage.removeItem).not.toHaveBeenCalledWith("token");
      } finally {
        // Restore the global so pretty-format and later tests are not poisoned.
        Object.keys = originalKeys;
      }
    });
  });

  describe("API Endpoints", () => {
    beforeEach(() => {
      fetch.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true }),
      });
    });

    it("makes correct request to dashboard endpoint", async () => {
      await mobileApiClient.getDashboardData();

      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:5000/api/v1/dashboard",
        expect.any(Object),
      );
    });

    it("makes correct request to transactions endpoint with params", async () => {
      const params = { limit: 10, offset: 0 };
      await mobileApiClient.getTransactions(params);

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/transactions?"),
        expect.any(Object),
      );
    });

    it("makes POST request with correct body", async () => {
      const accountData = { name: "Test Account", type: "asset" };
      await mobileApiClient.createAccount(accountData);

      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            "Content-Type": "application/json",
          }),
          body: JSON.stringify(accountData),
        }),
      );
    });

    it("fetches profile data", async () => {
      await mobileApiClient.getProfile();

      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:5000/api/v1/users/profile",
        expect.any(Object),
      );
    });

    it("refreshes auth token", async () => {
      await mobileApiClient.refreshToken();

      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:5000/api/v1/auth/refresh",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  describe("Connectivity", () => {
    it("returns true when health check succeeds", async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: "ok" }),
      });

      const result = await mobileApiClient.checkConnectivity();
      expect(result).toBe(true);
    });

    it("returns false when health check fails", async () => {
      fetch.mockRejectedValueOnce(new Error("Network error"));

      const result = await mobileApiClient.checkConnectivity();
      expect(result).toBe(false);
    });
  });
});
