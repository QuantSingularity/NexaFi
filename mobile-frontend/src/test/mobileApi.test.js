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
      expect(localStorage.setItem).toHaveBeenCalledWith("token", "test-token");
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

      expect(localStorage.removeItem).toHaveBeenCalledWith("token");
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
      expect(localStorage.removeItem).toHaveBeenCalledWith("token");

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
      Object.keys = vi.fn(() => [
        "cache_key1",
        "cache_key2",
        "other_key",
        "token",
      ]);

      mobileApiClient.clearCache();

      expect(localStorage.removeItem).toHaveBeenCalledWith("cache_key1");
      expect(localStorage.removeItem).toHaveBeenCalledWith("cache_key2");
      expect(localStorage.removeItem).not.toHaveBeenCalledWith("other_key");
      expect(localStorage.removeItem).not.toHaveBeenCalledWith("token");
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
        "http://localhost:5000/dashboard",
        expect.any(Object),
      );
    });

    it("makes correct request to transactions endpoint with params", async () => {
      const params = { limit: 10, offset: 0 };
      await mobileApiClient.getTransactions(params);

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/payments/transactions?"),
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
        "http://localhost:5000/users/profile",
        expect.any(Object),
      );
    });

    it("refreshes auth token", async () => {
      await mobileApiClient.refreshToken();

      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:5000/auth/refresh",
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
