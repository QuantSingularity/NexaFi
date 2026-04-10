import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowDownRight,
  ArrowUpRight,
  CreditCard,
  Download,
  Eye,
  EyeOff,
  Loader2,
  Plus,
  Search,
  Send,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApp, useAuth } from "../contexts/MobileContext";
import mobileApiClient from "../lib/mobileApi";

const MobilePaymentsModule = () => {
  const { user } = useAuth();
  const { addNotification, isOnline } = useApp();
  const [loading, setLoading] = useState(true);
  const [transactions, setTransactions] = useState([]);
  const [paymentMethods, setPaymentMethods] = useState([]);
  const [wallets, setWallets] = useState([]);
  const [selectedWallet, setSelectedWallet] = useState(null);
  const [balanceVisible, setBalanceVisible] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [isNewPaymentOpen, setIsNewPaymentOpen] = useState(false);
  const [isAddMethodOpen, setIsAddMethodOpen] = useState(false);
  const [processingPayment, setProcessingPayment] = useState(false);

  const [newPayment, setNewPayment] = useState({
    recipient: "",
    amount: "",
    currency: "USD",
    description: "",
    wallet_id: "",
  });

  const [newMethod, setNewMethod] = useState({
    type: "card",
    card_number: "",
    expiry_date: "",
    cvv: "",
    cardholder_name: "",
  });

  useEffect(() => {
    loadData();
  }, [loadData]);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);

      const [transactionsData, methodsData, walletsData] = await Promise.all([
        mobileApiClient.getTransactions().catch(() => []),
        mobileApiClient.getPaymentMethods().catch(() => []),
        mobileApiClient.getWallets().catch(() => []),
      ]);

      setTransactions(transactionsData.transactions || transactionsData || []);
      setPaymentMethods(methodsData.methods || methodsData || []);
      setWallets(walletsData.wallets || walletsData || []);

      if (walletsData.wallets && walletsData.wallets.length > 0) {
        setSelectedWallet(walletsData.wallets[0]);
      }
    } catch (error) {
      console.error("Failed to load payment data:", error);
      addNotification({
        type: "error",
        message: "Failed to load payment data",
      });
    } finally {
      setLoading(false);
    }
  }, [addNotification]);

  const handleSendPayment = async () => {
    if (!newPayment.recipient || !newPayment.amount || !newPayment.wallet_id) {
      addNotification({
        type: "error",
        message: "Please fill in all required fields",
      });
      return;
    }

    try {
      setProcessingPayment(true);

      const paymentData = {
        ...newPayment,
        amount: parseFloat(newPayment.amount),
        type: "outgoing",
        status: "pending",
      };

      const result = await mobileApiClient.createTransaction(paymentData);

      addNotification({
        type: "success",
        message: "Payment sent successfully!",
      });

      setTransactions((prev) => [result, ...prev]);
      setIsNewPaymentOpen(false);
      setNewPayment({
        recipient: "",
        amount: "",
        currency: "USD",
        description: "",
        wallet_id: "",
      });

      loadData();
    } catch (error) {
      console.error("Payment failed:", error);
      addNotification({
        type: "error",
        message: error.message || "Payment failed. Please try again.",
      });
    } finally {
      setProcessingPayment(false);
    }
  };

  const handleAddPaymentMethod = async () => {
    if (
      !newMethod.card_number ||
      !newMethod.expiry_date ||
      !newMethod.cvv ||
      !newMethod.cardholder_name
    ) {
      addNotification({
        type: "error",
        message: "Please fill in all card details",
      });
      return;
    }

    try {
      const result = await mobileApiClient.addPaymentMethod(newMethod);

      addNotification({
        type: "success",
        message: "Payment method added successfully!",
      });

      setPaymentMethods((prev) => [...prev, result]);
      setIsAddMethodOpen(false);
      setNewMethod({
        type: "card",
        card_number: "",
        expiry_date: "",
        cvv: "",
        cardholder_name: "",
      });
    } catch (error) {
      console.error("Failed to add payment method:", error);
      addNotification({
        type: "error",
        message: "Failed to add payment method",
      });
    }
  };

  const filteredTransactions = transactions.filter((transaction) => {
    const matchesSearch =
      transaction.description
        ?.toLowerCase()
        .includes(searchQuery.toLowerCase()) ||
      transaction.recipient?.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesFilter =
      filterType === "all" ||
      transaction.type === filterType ||
      transaction.status === filterType;

    return matchesSearch && matchesFilter;
  });

  const getStatusColor = (status) => {
    switch (status) {
      case "completed":
        return "bg-green-100 text-green-700";
      case "pending":
        return "bg-yellow-100 text-yellow-700";
      case "failed":
        return "bg-red-100 text-red-700";
      default:
        return "bg-gray-100 text-gray-700";
    }
  };

  const getTransactionIcon = (type) => {
    return type === "incoming" ? (
      <ArrowDownRight className="h-5 w-5 text-green-600" />
    ) : (
      <ArrowUpRight className="h-5 w-5 text-red-600" />
    );
  };

  const formatCurrency = (amount, currency = "USD") => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency,
    }).format(amount);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      {/* Header with Wallet Balance */}
      <div className="bg-gradient-to-br from-blue-600 to-blue-700 text-white p-6 rounded-b-3xl">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold">Payments</h1>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setBalanceVisible(!balanceVisible)}
              className="text-white hover:bg-white/20"
              aria-label="Toggle balance visibility"
            >
              {balanceVisible ? (
                <Eye className="h-5 w-5" />
              ) : (
                <EyeOff className="h-5 w-5" />
              )}
            </Button>
          </div>

          {selectedWallet && (
            <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-4">
              <p className="text-sm text-blue-100 mb-1">Total Balance</p>
              <div className="flex items-baseline gap-2">
                {balanceVisible ? (
                  <>
                    <span className="text-4xl font-bold">
                      {formatCurrency(selectedWallet.balance || 0)}
                    </span>
                    <span className="text-blue-100">
                      {selectedWallet.currency || "USD"}
                    </span>
                  </>
                ) : (
                  <span className="text-4xl font-bold">••••••</span>
                )}
              </div>
            </div>
          )}

          {/* Quick Actions */}
          <div className="grid grid-cols-2 gap-3 pt-2">
            <Dialog open={isNewPaymentOpen} onOpenChange={setIsNewPaymentOpen}>
              <DialogTrigger asChild>
                <Button className="bg-white text-blue-600 hover:bg-blue-50">
                  <Send className="h-4 w-4 mr-2" />
                  Send Money
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Send Payment</DialogTitle>
                  <DialogDescription>
                    Transfer money to another account
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 pt-4">
                  <div>
                    <Label htmlFor="recipient">Recipient</Label>
                    <Input
                      id="recipient"
                      placeholder="Email or account number"
                      value={newPayment.recipient}
                      onChange={(e) =>
                        setNewPayment({
                          ...newPayment,
                          recipient: e.target.value,
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label htmlFor="amount">Amount</Label>
                    <Input
                      id="amount"
                      type="number"
                      placeholder="0.00"
                      value={newPayment.amount}
                      onChange={(e) =>
                        setNewPayment({ ...newPayment, amount: e.target.value })
                      }
                    />
                  </div>
                  <div>
                    <Label htmlFor="wallet">From Wallet</Label>
                    <Select
                      value={newPayment.wallet_id}
                      onValueChange={(value) =>
                        setNewPayment({ ...newPayment, wallet_id: value })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select wallet" />
                      </SelectTrigger>
                      <SelectContent>
                        {wallets.map((wallet) => (
                          <SelectItem
                            key={wallet.id}
                            value={wallet.id.toString()}
                          >
                            {wallet.name} ({formatCurrency(wallet.balance)})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="description">Description (Optional)</Label>
                    <Input
                      id="description"
                      placeholder="What's this for?"
                      value={newPayment.description}
                      onChange={(e) =>
                        setNewPayment({
                          ...newPayment,
                          description: e.target.value,
                        })
                      }
                    />
                  </div>
                  <Button
                    onClick={handleSendPayment}
                    disabled={processingPayment || !isOnline}
                    className="w-full"
                  >
                    {processingPayment ? (
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    ) : (
                      <Send className="h-4 w-4 mr-2" />
                    )}
                    Send Payment
                  </Button>
                </div>
              </DialogContent>
            </Dialog>

            <Button
              variant="outline"
              className="bg-white/10 text-white border-white/20 hover:bg-white/20"
              onClick={() => {
                addNotification({
                  type: "info",
                  message: "Request money feature coming soon!",
                });
              }}
            >
              <Download className="h-4 w-4 mr-2" />
              Request
            </Button>
          </div>
        </motion.div>
      </div>

      {/* Main Content */}
      <div className="p-4 space-y-4">
        <Tabs defaultValue="transactions" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="transactions">Transactions</TabsTrigger>
            <TabsTrigger value="methods">Payment Methods</TabsTrigger>
          </TabsList>

          <TabsContent value="transactions" className="space-y-4">
            {/* Search and Filter */}
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search transactions..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
              <Select value={filterType} onValueChange={setFilterType}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="incoming">Incoming</SelectItem>
                  <SelectItem value="outgoing">Outgoing</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Transaction List */}
            <div className="space-y-3">
              <AnimatePresence>
                {filteredTransactions.length === 0 ? (
                  <Card>
                    <CardContent className="flex flex-col items-center justify-center py-12">
                      <CreditCard className="h-12 w-12 text-gray-400 mb-4" />
                      <p className="text-gray-600 text-center">
                        No transactions found
                      </p>
                      <p className="text-sm text-gray-400 text-center mt-2">
                        Your transaction history will appear here
                      </p>
                    </CardContent>
                  </Card>
                ) : (
                  filteredTransactions.map((transaction, index) => (
                    <motion.div
                      key={transaction.id || index}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -20 }}
                      transition={{ delay: index * 0.05 }}
                    >
                      <Card>
                        <CardContent className="p-4">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <div className="p-2 bg-gray-100 rounded-full">
                                {getTransactionIcon(transaction.type)}
                              </div>
                              <div>
                                <p className="font-medium">
                                  {transaction.recipient ||
                                    transaction.description ||
                                    "Transaction"}
                                </p>
                                <p className="text-sm text-gray-500">
                                  {transaction.created_at
                                    ? new Date(
                                        transaction.created_at,
                                      ).toLocaleDateString()
                                    : "Recent"}
                                </p>
                              </div>
                            </div>
                            <div className="text-right">
                              <p
                                className={`font-semibold ${
                                  transaction.type === "incoming"
                                    ? "text-green-600"
                                    : "text-red-600"
                                }`}
                              >
                                {transaction.type === "incoming" ? "+" : "-"}
                                {formatCurrency(
                                  transaction.amount,
                                  transaction.currency,
                                )}
                              </p>
                              <Badge
                                className={getStatusColor(transaction.status)}
                              >
                                {transaction.status}
                              </Badge>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    </motion.div>
                  ))
                )}
              </AnimatePresence>
            </div>
          </TabsContent>

          <TabsContent value="methods" className="space-y-4">
            <Dialog open={isAddMethodOpen} onOpenChange={setIsAddMethodOpen}>
              <DialogTrigger asChild>
                <Button className="w-full">
                  <Plus className="h-4 w-4 mr-2" />
                  Add Payment Method
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Add Payment Method</DialogTitle>
                  <DialogDescription>
                    Add a new card or bank account
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 pt-4">
                  <div>
                    <Label htmlFor="cardholder">Cardholder Name</Label>
                    <Input
                      id="cardholder"
                      placeholder="John Doe"
                      value={newMethod.cardholder_name}
                      onChange={(e) =>
                        setNewMethod({
                          ...newMethod,
                          cardholder_name: e.target.value,
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label htmlFor="card_number">Card Number</Label>
                    <Input
                      id="card_number"
                      placeholder="1234 5678 9012 3456"
                      value={newMethod.card_number}
                      onChange={(e) =>
                        setNewMethod({
                          ...newMethod,
                          card_number: e.target.value,
                        })
                      }
                      maxLength={19}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="expiry">Expiry Date</Label>
                      <Input
                        id="expiry"
                        placeholder="MM/YY"
                        value={newMethod.expiry_date}
                        onChange={(e) =>
                          setNewMethod({
                            ...newMethod,
                            expiry_date: e.target.value,
                          })
                        }
                        maxLength={5}
                      />
                    </div>
                    <div>
                      <Label htmlFor="cvv">CVV</Label>
                      <Input
                        id="cvv"
                        placeholder="123"
                        type="password"
                        value={newMethod.cvv}
                        onChange={(e) =>
                          setNewMethod({ ...newMethod, cvv: e.target.value })
                        }
                        maxLength={4}
                      />
                    </div>
                  </div>
                  <Button
                    onClick={handleAddPaymentMethod}
                    disabled={!isOnline}
                    className="w-full"
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Add Card
                  </Button>
                </div>
              </DialogContent>
            </Dialog>

            {/* Payment Methods List */}
            <div className="space-y-3">
              {paymentMethods.length === 0 ? (
                <Card>
                  <CardContent className="flex flex-col items-center justify-center py-12">
                    <CreditCard className="h-12 w-12 text-gray-400 mb-4" />
                    <p className="text-gray-600 text-center">
                      No payment methods added
                    </p>
                    <p className="text-sm text-gray-400 text-center mt-2">
                      Add a card or bank account to get started
                    </p>
                  </CardContent>
                </Card>
              ) : (
                paymentMethods.map((method) => (
                  <Card key={method.id}>
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-blue-100 rounded-full">
                            <CreditCard className="h-5 w-5 text-blue-600" />
                          </div>
                          <div>
                            <p className="font-medium">
                              {method.type === "card" ? "Card" : "Bank Account"}
                            </p>
                            <p className="text-sm text-gray-500">
                              ••••{" "}
                              {method.card_number?.slice(-4) ||
                                method.account_number?.slice(-4) ||
                                "****"}
                            </p>
                          </div>
                        </div>
                        {method.is_default && (
                          <Badge className="bg-blue-100 text-blue-700">
                            Default
                          </Badge>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))
              )}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default MobilePaymentsModule;
