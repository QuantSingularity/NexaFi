import {
  ArrowDownLeft,
  ArrowUpRight,
  CheckCircle,
  Clock,
  CreditCard,
  DollarSign,
  Download,
  Edit,
  Eye,
  Filter,
  Plus,
  Trash2,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApp } from "../contexts/AppContext";
import apiClient from "../lib/api";

const PaymentsModule = () => {
  const { addNotification } = useApp();
  const [activeTab, setActiveTab] = useState("overview");
  const [_paymentMethods, setPaymentMethods] = useState([]);
  const [_transactions, setTransactions] = useState([]);
  const [_wallets, setWallets] = useState([]);
  const [_analytics, setAnalytics] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPaymentData();
  }, [loadPaymentData]);

  const loadPaymentData = async () => {
    try {
      setLoading(true);

      // Load payment methods
      const methodsResponse = await apiClient.getPaymentMethods();
      setPaymentMethods(methodsResponse.payment_methods || []);

      // Load transactions
      const transactionsResponse = await apiClient.getTransactions({
        per_page: 20,
      });
      setTransactions(transactionsResponse.transactions || []);

      // Load wallets
      const walletsResponse = await apiClient.getWallets();
      setWallets(walletsResponse.wallets || []);

      // Load analytics
      const endDate = new Date().toISOString().split("T")[0];
      const startDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
        .toISOString()
        .split("T")[0];
      const analyticsResponse = await apiClient.getPaymentAnalytics(
        startDate,
        endDate,
      );
      setAnalytics(analyticsResponse);
    } catch (error) {
      console.error("Failed to load payment data:", error);
      addNotification({
        type: "error",
        title: "Error",
        message: "Failed to load payment data",
      });
    } finally {
      setLoading(false);
    }
  };

  const PaymentOverview = () => {
    const mockAnalyticsData = [
      { month: "Jan", income: 45000, expenses: 32000 },
      { month: "Feb", income: 52000, expenses: 35000 },
      { month: "Mar", income: 48000, expenses: 33000 },
      { month: "Apr", income: 61000, expenses: 38000 },
      { month: "May", income: 55000, expenses: 36000 },
      { month: "Jun", income: 58000, expenses: 39000 },
    ];

    return (
      <div className="space-y-6">
        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">
                    Total Volume
                  </p>
                  <p className="text-2xl font-bold text-gray-900">$125,430</p>
                  <div className="flex items-center mt-2 text-sm text-green-600">
                    <TrendingUp className="w-4 h-4 mr-1" />
                    +12% from last month
                  </div>
                </div>
                <div className="p-3 rounded-full bg-blue-100">
                  <DollarSign className="w-6 h-6 text-blue-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">
                    Transactions
                  </p>
                  <p className="text-2xl font-bold text-gray-900">1,247</p>
                  <div className="flex items-center mt-2 text-sm text-green-600">
                    <TrendingUp className="w-4 h-4 mr-1" />
                    +8% from last month
                  </div>
                </div>
                <div className="p-3 rounded-full bg-green-100">
                  <ArrowUpRight className="w-6 h-6 text-green-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">
                    Success Rate
                  </p>
                  <p className="text-2xl font-bold text-gray-900">98.5%</p>
                  <div className="flex items-center mt-2 text-sm text-green-600">
                    <CheckCircle className="w-4 h-4 mr-1" />
                    +0.3% from last month
                  </div>
                </div>
                <div className="p-3 rounded-full bg-purple-100">
                  <CheckCircle className="w-6 h-6 text-purple-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">
                    Avg. Transaction
                  </p>
                  <p className="text-2xl font-bold text-gray-900">$1,005</p>
                  <div className="flex items-center mt-2 text-sm text-blue-600">
                    <TrendingUp className="w-4 h-4 mr-1" />
                    +5% from last month
                  </div>
                </div>
                <div className="p-3 rounded-full bg-yellow-100">
                  <CreditCard className="w-6 h-6 text-yellow-600" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Payment Volume Trend</CardTitle>
              <CardDescription>
                Monthly payment volume over time
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={mockAnalyticsData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" />
                  <YAxis />
                  <Tooltip
                    formatter={(value) => [`$${value.toLocaleString()}`, ""]}
                  />
                  <Area
                    type="monotone"
                    dataKey="income"
                    stroke="#3b82f6"
                    fill="#3b82f6"
                    fillOpacity={0.6}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Wallet Balances</CardTitle>
              <CardDescription>
                Current balances across all wallets
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                      <DollarSign className="w-4 h-4 text-blue-600" />
                    </div>
                    <div>
                      <p className="font-medium">USD Wallet</p>
                      <p className="text-sm text-gray-500">Primary currency</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-bold">$25,430.50</p>
                    <p className="text-sm text-green-600">Available</p>
                  </div>
                </div>

                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                      <DollarSign className="w-4 h-4 text-green-600" />
                    </div>
                    <div>
                      <p className="font-medium">EUR Wallet</p>
                      <p className="text-sm text-gray-500">
                        Secondary currency
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-bold">€12,850.25</p>
                    <p className="text-sm text-green-600">Available</p>
                  </div>
                </div>

                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center">
                      <DollarSign className="w-4 h-4 text-purple-600" />
                    </div>
                    <div>
                      <p className="font-medium">GBP Wallet</p>
                      <p className="text-sm text-gray-500">
                        Additional currency
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-bold">£8,920.75</p>
                    <p className="text-sm text-green-600">Available</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  };

  const PaymentMethods = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Payment Methods</h2>
        <Dialog>
          <DialogTrigger asChild>
            <Button>
              <Plus className="w-4 h-4 mr-2" />
              Add Payment Method
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Payment Method</DialogTitle>
              <DialogDescription>
                Add a new payment method to your account
              </DialogDescription>
            </DialogHeader>
            <AddPaymentMethodForm onSuccess={loadPaymentData} />
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Mock payment methods */}
        <Card className="hover:shadow-lg transition-shadow">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                  <CreditCard className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <p className="font-medium">Visa •••• 4242</p>
                  <p className="text-sm text-gray-500">Expires 12/25</p>
                </div>
              </div>
              <Badge>Default</Badge>
            </div>
            <div className="flex space-x-2">
              <Button variant="outline" size="sm" className="flex-1">
                <Edit className="w-4 h-4 mr-2" />
                Edit
              </Button>
              <Button variant="outline" size="sm">
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="hover:shadow-lg transition-shadow">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                  <Wallet className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <p className="font-medium">Bank Account •••• 1234</p>
                  <p className="text-sm text-gray-500">Chase Bank</p>
                </div>
              </div>
              <Badge variant="outline">Verified</Badge>
            </div>
            <div className="flex space-x-2">
              <Button variant="outline" size="sm" className="flex-1">
                <Edit className="w-4 h-4 mr-2" />
                Edit
              </Button>
              <Button variant="outline" size="sm">
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="border-dashed border-2 hover:border-blue-300 transition-colors cursor-pointer">
          <CardContent className="p-6 flex flex-col items-center justify-center text-center">
            <Plus className="w-8 h-8 text-gray-400 mb-2" />
            <p className="font-medium text-gray-600">Add Payment Method</p>
            <p className="text-sm text-gray-500">
              Credit card, bank account, or digital wallet
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );

  const TransactionHistory = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Transaction History</h2>
        <div className="flex space-x-2">
          <Button variant="outline">
            <Filter className="w-4 h-4 mr-2" />
            Filter
          </Button>
          <Button variant="outline">
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
          <Dialog>
            <DialogTrigger asChild>
              <Button>
                <Plus className="w-4 h-4 mr-2" />
                New Transaction
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create Transaction</DialogTitle>
                <DialogDescription>
                  Process a new payment or transfer
                </DialogDescription>
              </DialogHeader>
              <CreateTransactionForm onSuccess={loadPaymentData} />
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <Card>
        <CardContent className="p-6">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Transaction ID</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {/* Mock transactions */}
              <TableRow>
                <TableCell className="font-mono">TXN-001</TableCell>
                <TableCell>2024-06-10</TableCell>
                <TableCell>Client Payment - ABC Corp</TableCell>
                <TableCell>
                  <Badge variant="outline" className="text-green-600">
                    <ArrowUpRight className="w-3 h-3 mr-1" />
                    Income
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-green-600">
                  +$5,000.00
                </TableCell>
                <TableCell>
                  <Badge>
                    <CheckCircle className="w-3 h-3 mr-1" />
                    Completed
                  </Badge>
                </TableCell>
                <TableCell>
                  <Button variant="ghost" size="sm">
                    <Eye className="w-4 h-4" />
                  </Button>
                </TableCell>
              </TableRow>

              <TableRow>
                <TableCell className="font-mono">TXN-002</TableCell>
                <TableCell>2024-06-09</TableCell>
                <TableCell>Office Rent Payment</TableCell>
                <TableCell>
                  <Badge variant="outline" className="text-red-600">
                    <ArrowDownLeft className="w-3 h-3 mr-1" />
                    Expense
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-red-600">
                  -$2,500.00
                </TableCell>
                <TableCell>
                  <Badge>
                    <CheckCircle className="w-3 h-3 mr-1" />
                    Completed
                  </Badge>
                </TableCell>
                <TableCell>
                  <Button variant="ghost" size="sm">
                    <Eye className="w-4 h-4" />
                  </Button>
                </TableCell>
              </TableRow>

              <TableRow>
                <TableCell className="font-mono">TXN-003</TableCell>
                <TableCell>2024-06-08</TableCell>
                <TableCell>Software Subscription</TableCell>
                <TableCell>
                  <Badge variant="outline" className="text-red-600">
                    <ArrowDownLeft className="w-3 h-3 mr-1" />
                    Expense
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-red-600">
                  -$299.00
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">
                    <Clock className="w-3 h-3 mr-1" />
                    Processing
                  </Badge>
                </TableCell>
                <TableCell>
                  <Button variant="ghost" size="sm">
                    <Eye className="w-4 h-4" />
                  </Button>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-32 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Payments</h1>
        <p className="text-gray-600 mt-1">
          Manage payment methods, transactions, and wallets
        </p>
      </div>

      <Tabs
        value={activeTab}
        onValueChange={setActiveTab}
        className="space-y-6"
      >
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="methods">Payment Methods</TabsTrigger>
          <TabsTrigger value="transactions">Transactions</TabsTrigger>
          <TabsTrigger value="wallets">Wallets</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <PaymentOverview />
        </TabsContent>

        <TabsContent value="methods">
          <PaymentMethods />
        </TabsContent>

        <TabsContent value="transactions">
          <TransactionHistory />
        </TabsContent>

        <TabsContent value="wallets">
          <PaymentOverview />
        </TabsContent>
      </Tabs>
    </div>
  );
};

// Add Payment Method Form
const AddPaymentMethodForm = ({ onSuccess }) => {
  const [formData, setFormData] = useState({
    type: "card",
    provider: "stripe",
    details: {
      last_four: "",
      brand: "",
      exp_month: "",
      exp_year: "",
    },
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await apiClient.createPaymentMethod(formData);
      onSuccess();
    } catch (error) {
      console.error("Failed to add payment method:", error);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <Label htmlFor="type">Payment Type</Label>
        <Select
          value={formData.type}
          onValueChange={(value) =>
            setFormData((prev) => ({ ...prev, type: value }))
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="card">Credit/Debit Card</SelectItem>
            <SelectItem value="bank_account">Bank Account</SelectItem>
            <SelectItem value="digital_wallet">Digital Wallet</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {formData.type === "card" && (
        <>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="last_four">Last 4 Digits</Label>
              <Input
                id="last_four"
                value={formData.details.last_four}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    details: { ...prev.details, last_four: e.target.value },
                  }))
                }
                placeholder="4242"
                maxLength={4}
              />
            </div>
            <div>
              <Label htmlFor="brand">Card Brand</Label>
              <Select
                value={formData.details.brand}
                onValueChange={(value) =>
                  setFormData((prev) => ({
                    ...prev,
                    details: { ...prev.details, brand: value },
                  }))
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select brand" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="visa">Visa</SelectItem>
                  <SelectItem value="mastercard">Mastercard</SelectItem>
                  <SelectItem value="amex">American Express</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="exp_month">Expiry Month</Label>
              <Input
                id="exp_month"
                type="number"
                min="1"
                max="12"
                value={formData.details.exp_month}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    details: { ...prev.details, exp_month: e.target.value },
                  }))
                }
                placeholder="12"
              />
            </div>
            <div>
              <Label htmlFor="exp_year">Expiry Year</Label>
              <Input
                id="exp_year"
                type="number"
                min="2024"
                max="2034"
                value={formData.details.exp_year}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    details: { ...prev.details, exp_year: e.target.value },
                  }))
                }
                placeholder="2025"
              />
            </div>
          </div>
        </>
      )}

      <Button type="submit" className="w-full">
        Add Payment Method
      </Button>
    </form>
  );
};

// Create Transaction Form
const CreateTransactionForm = ({ onSuccess }) => {
  const [formData, setFormData] = useState({
    transaction_type: "payment",
    amount: "",
    currency: "USD",
    description: "",
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await apiClient.createTransaction(formData);
      onSuccess();
    } catch (error) {
      console.error("Failed to create transaction:", error);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <Label htmlFor="transaction_type">Transaction Type</Label>
        <Select
          value={formData.transaction_type}
          onValueChange={(value) =>
            setFormData((prev) => ({ ...prev, transaction_type: value }))
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="payment">Payment</SelectItem>
            <SelectItem value="transfer">Transfer</SelectItem>
            <SelectItem value="withdrawal">Withdrawal</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="amount">Amount</Label>
          <Input
            id="amount"
            type="number"
            step="0.01"
            value={formData.amount}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, amount: e.target.value }))
            }
            placeholder="0.00"
            required
          />
        </div>
        <div>
          <Label htmlFor="currency">Currency</Label>
          <Select
            value={formData.currency}
            onValueChange={(value) =>
              setFormData((prev) => ({ ...prev, currency: value }))
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="USD">USD</SelectItem>
              <SelectItem value="EUR">EUR</SelectItem>
              <SelectItem value="GBP">GBP</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div>
        <Label htmlFor="description">Description</Label>
        <Input
          id="description"
          value={formData.description}
          onChange={(e) =>
            setFormData((prev) => ({ ...prev, description: e.target.value }))
          }
          placeholder="Transaction description"
          required
        />
      </div>

      <Button type="submit" className="w-full">
        Create Transaction
      </Button>
    </form>
  );
};

export default PaymentsModule;
