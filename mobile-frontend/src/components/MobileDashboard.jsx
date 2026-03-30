import { motion } from "framer-motion";
import {
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  CreditCard,
  DollarSign,
  Eye,
  EyeOff,
  Plus,
  RefreshCw,
  Target,
  TrendingUp,
  Zap,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Area, AreaChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useApp, useAuth } from "../contexts/MobileContext";
import mobileApiClient from "../lib/mobileApi";
import "../App.css";

const MobileDashboard = () => {
  const { user } = useAuth();
  const { addNotification, isOnline } = useApp();
  const [loading, setLoading] = useState(true);
  const [balanceVisible, setBalanceVisible] = useState(true);
  const [dashboardData, setDashboardData] = useState({
    totalBalance: 125430.5,
    monthlyIncome: 45200.0,
    monthlyExpenses: 32100.0,
    cashFlow: 13100.0,
    accounts: 8,
    transactions: 156,
    pendingPayments: 3,
  });

  const [recentTransactions] = useState([
    {
      id: 1,
      description: "Client Payment - ABC Corp",
      amount: 5000,
      type: "income",
      date: "2024-06-10",
    },
    {
      id: 2,
      description: "Office Rent",
      amount: -2500,
      type: "expense",
      date: "2024-06-09",
    },
    {
      id: 3,
      description: "Software Subscription",
      amount: -299,
      type: "expense",
      date: "2024-06-09",
    },
    {
      id: 4,
      description: "Consulting Fee",
      amount: 3500,
      type: "income",
      date: "2024-06-08",
    },
  ]);

  const [chartData] = useState([
    { month: "Jan", income: 42000, expenses: 28000 },
    { month: "Feb", income: 38000, expenses: 31000 },
    { month: "Mar", income: 45000, expenses: 29000 },
    { month: "Apr", income: 48000, expenses: 33000 },
    { month: "May", income: 52000, expenses: 35000 },
    { month: "Jun", income: 45200, expenses: 32100 },
  ]);

  const [_expenseData] = useState([
    { name: "Operations", value: 45, color: "#3b82f6" },
    { name: "Marketing", value: 25, color: "#8b5cf6" },
    { name: "Technology", value: 20, color: "#06b6d4" },
    { name: "Other", value: 10, color: "#10b981" },
  ]);

  const [quickActions] = useState([
    {
      icon: Plus,
      label: "Add Transaction",
      action: "add-transaction",
      color: "bg-blue-500",
    },
    {
      icon: CreditCard,
      label: "Make Payment",
      action: "make-payment",
      color: "bg-green-500",
    },
    {
      icon: BarChart3,
      label: "View Reports",
      action: "view-reports",
      color: "bg-purple-500",
    },
    {
      icon: Zap,
      label: "Quick Transfer",
      action: "quick-transfer",
      color: "bg-orange-500",
    },
  ]);

  const [insights] = useState([
    {
      type: "positive",
      title: "Cash Flow Improved",
      description: "Your cash flow increased by 15% this month",
      icon: TrendingUp,
      color: "text-green-600",
    },
    {
      type: "warning",
      title: "High Expenses",
      description: "Marketing expenses are 20% above budget",
      icon: AlertCircle,
      color: "text-orange-600",
    },
    {
      type: "info",
      title: "Payment Due",
      description: "3 invoices are due for payment this week",
      icon: Target,
      color: "text-blue-600",
    },
  ]);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  const loadDashboardData = async () => {
    try {
      setLoading(true);

      if (isOnline) {
        // Try to fetch fresh data
        const data = await mobileApiClient.getDashboardData();
        setDashboardData(data);
      } else {
        // Use cached data when offline
        const cachedData = mobileApiClient.getCachedData("dashboard");
        if (cachedData) {
          setDashboardData(cachedData);
          addNotification({
            type: "info",
            title: "Offline Mode",
            message: "Showing cached data",
          });
        }
      }
    } catch (error) {
      console.error("Failed to load dashboard data:", error);
      addNotification({
        type: "error",
        title: "Error",
        message: "Failed to load dashboard data",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleQuickAction = (action) => {
    addNotification({
      type: "info",
      title: "Quick Action",
      message: `${action} feature coming soon!`,
    });
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(amount);
  };

  if (loading) {
    return (
      <div className="p-4">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/2"></div>
          <div className="grid grid-cols-2 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-gray-200 rounded"></div>
            ))}
          </div>
          <div className="h-48 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-6 pb-20">
      {/* Welcome Section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6"
      >
        <h2 className="text-xl font-bold text-gray-900 mb-1">
          Welcome back, {user?.first_name}!
        </h2>
        <p className="text-gray-600 text-sm">
          Here's your financial overview for today
        </p>
      </motion.div>

      {/* Balance Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <Card className="bg-gradient-to-r from-blue-600 to-purple-600 text-white border-0">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-blue-100 text-sm">Total Balance</p>
                <div className="flex items-center space-x-2">
                  <p className="text-2xl font-bold">
                    {balanceVisible
                      ? formatCurrency(dashboardData.totalBalance)
                      : "••••••"}
                  </p>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setBalanceVisible(!balanceVisible)}
                    className="text-white hover:bg-white/20 p-1"
                  >
                    {balanceVisible ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </Button>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={loadDashboardData}
                className="text-white hover:bg-white/20"
              >
                <RefreshCw className="w-4 h-4" />
              </Button>
            </div>

            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-1">
                <TrendingUp className="w-4 h-4 text-green-300" />
                <span className="text-sm text-blue-100">+12.5% this month</span>
              </div>
              {!isOnline && (
                <Badge
                  variant="secondary"
                  className="bg-orange-500/20 text-orange-100"
                >
                  Offline
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Quick Stats */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="grid grid-cols-2 gap-4"
      >
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                <ArrowUpRight className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="text-xs text-gray-600">Income</p>
                <p className="text-lg font-bold text-gray-900">
                  {formatCurrency(dashboardData.monthlyIncome)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
                <ArrowDownRight className="w-5 h-5 text-red-600" />
              </div>
              <div>
                <p className="text-xs text-gray-600">Expenses</p>
                <p className="text-lg font-bold text-gray-900">
                  {formatCurrency(dashboardData.monthlyExpenses)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                <DollarSign className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <p className="text-xs text-gray-600">Cash Flow</p>
                <p className="text-lg font-bold text-green-600">
                  {formatCurrency(dashboardData.cashFlow)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                <CreditCard className="w-5 h-5 text-purple-600" />
              </div>
              <div>
                <p className="text-xs text-gray-600">Pending</p>
                <p className="text-lg font-bold text-orange-600">
                  {dashboardData.pendingPayments}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Quick Actions */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Quick Actions
        </h3>
        <div className="grid grid-cols-2 gap-3">
          {quickActions.map((action, index) => {
            const Icon = action.icon;
            return (
              <motion.button
                key={index}
                onClick={() => handleQuickAction(action.action)}
                className="flex flex-col items-center space-y-2 p-4 bg-white rounded-lg border border-gray-200 hover:shadow-md transition-shadow"
                whileTap={{ scale: 0.98 }}
              >
                <div
                  className={`w-12 h-12 ${action.color} rounded-lg flex items-center justify-center`}
                >
                  <Icon className="w-6 h-6 text-white" />
                </div>
                <span className="text-sm font-medium text-gray-900">
                  {action.label}
                </span>
              </motion.button>
            );
          })}
        </div>
      </motion.div>

      {/* Chart */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Income vs Expenses</CardTitle>
            <CardDescription>Last 6 months comparison</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={chartData}>
                <XAxis dataKey="month" axisLine={false} tickLine={false} />
                <YAxis hide />
                <Area
                  type="monotone"
                  dataKey="income"
                  stackId="1"
                  stroke="#3b82f6"
                  fill="#3b82f6"
                  fillOpacity={0.6}
                />
                <Area
                  type="monotone"
                  dataKey="expenses"
                  stackId="2"
                  stroke="#ef4444"
                  fill="#ef4444"
                  fillOpacity={0.6}
                />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </motion.div>

      {/* AI Insights */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
      >
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          AI Insights
        </h3>
        <div className="space-y-3">
          {insights.map((insight, index) => {
            const Icon = insight.icon;
            return (
              <Card key={index} className="border-l-4 border-l-blue-500">
                <CardContent className="p-4">
                  <div className="flex items-start space-x-3">
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        insight.type === "positive"
                          ? "bg-green-100"
                          : insight.type === "warning"
                            ? "bg-orange-100"
                            : "bg-blue-100"
                      }`}
                    >
                      <Icon className={`w-4 h-4 ${insight.color}`} />
                    </div>
                    <div className="flex-1">
                      <h4 className="font-medium text-gray-900 text-sm">
                        {insight.title}
                      </h4>
                      <p className="text-xs text-gray-600 mt-1">
                        {insight.description}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </motion.div>

      {/* Recent Transactions */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">
            Recent Transactions
          </h3>
          <Button variant="ghost" size="sm" className="text-blue-600">
            View All
          </Button>
        </div>
        <div className="space-y-3">
          {recentTransactions.map((transaction) => (
            <Card key={transaction.id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div
                      className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                        transaction.type === "income"
                          ? "bg-green-100"
                          : "bg-red-100"
                      }`}
                    >
                      {transaction.type === "income" ? (
                        <ArrowUpRight className="w-5 h-5 text-green-600" />
                      ) : (
                        <ArrowDownRight className="w-5 h-5 text-red-600" />
                      )}
                    </div>
                    <div>
                      <p className="font-medium text-gray-900 text-sm">
                        {transaction.description}
                      </p>
                      <p className="text-xs text-gray-500">
                        {transaction.date}
                      </p>
                    </div>
                  </div>
                  <p
                    className={`font-bold ${
                      transaction.type === "income"
                        ? "text-green-600"
                        : "text-red-600"
                    }`}
                  >
                    {transaction.type === "income" ? "+" : ""}
                    {formatCurrency(transaction.amount)}
                  </p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </motion.div>
    </div>
  );
};

export default MobileDashboard;
