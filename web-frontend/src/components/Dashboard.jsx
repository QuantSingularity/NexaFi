import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Brain,
  CheckCircle,
  Clock,
  CreditCard,
  DollarSign,
  PieChart,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart as RechartsPieChart,
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
import { useApp, useAuth } from "../contexts/AppContext";

const Dashboard = () => {
  const { user } = useAuth();
  const { addNotification } = useApp();
  const [dashboardData, setDashboardData] = useState({
    metrics: {
      totalRevenue: 0,
      totalExpenses: 0,
      netIncome: 0,
      cashFlow: 0,
      accountsReceivable: 0,
      accountsPayable: 0,
    },
    insights: [],
    recentTransactions: [],
    cashFlowData: [],
    expenseBreakdown: [],
    loading: true,
  });

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  const loadDashboardData = async () => {
    try {
      // Simulate loading dashboard data
      const mockData = {
        metrics: {
          totalRevenue: 125000,
          totalExpenses: 87500,
          netIncome: 37500,
          cashFlow: 15000,
          accountsReceivable: 25000,
          accountsPayable: 12000,
        },
        insights: [
          {
            id: 1,
            title: "Cash Flow Improving",
            description: "Your cash flow has increased by 15% this month",
            type: "positive",
            severity: "info",
          },
          {
            id: 2,
            title: "High Expense Alert",
            description: "Marketing expenses are 40% above average",
            type: "warning",
            severity: "warning",
          },
          {
            id: 3,
            title: "Payment Due Soon",
            description: "3 invoices totaling $8,500 due in 5 days",
            type: "reminder",
            severity: "info",
          },
        ],
        recentTransactions: [
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
            date: "2024-06-08",
          },
          {
            id: 4,
            description: "Consulting Revenue",
            amount: 3500,
            type: "income",
            date: "2024-06-07",
          },
          {
            id: 5,
            description: "Marketing Campaign",
            amount: -1200,
            type: "expense",
            date: "2024-06-06",
          },
        ],
        cashFlowData: [
          { month: "Jan", income: 45000, expenses: 32000, net: 13000 },
          { month: "Feb", income: 52000, expenses: 35000, net: 17000 },
          { month: "Mar", income: 48000, expenses: 33000, net: 15000 },
          { month: "Apr", income: 61000, expenses: 38000, net: 23000 },
          { month: "May", income: 55000, expenses: 36000, net: 19000 },
          { month: "Jun", income: 58000, expenses: 39000, net: 19000 },
        ],
        expenseBreakdown: [
          { name: "Salaries", value: 35000, color: "#3b82f6" },
          { name: "Rent", value: 15000, color: "#8b5cf6" },
          { name: "Marketing", value: 12000, color: "#06b6d4" },
          { name: "Software", value: 8000, color: "#10b981" },
          { name: "Utilities", value: 5000, color: "#f59e0b" },
          { name: "Other", value: 12500, color: "#ef4444" },
        ],
      };

      setDashboardData({ ...mockData, loading: false });
    } catch (error) {
      console.error("Failed to load dashboard data:", error);
      addNotification({
        type: "error",
        title: "Error",
        message: "Failed to load dashboard data",
      });
      setDashboardData((prev) => ({ ...prev, loading: false }));
    }
  };

  const MetricCard = ({ title, value, change, icon: Icon, trend }) => (
    <Card className="hover:shadow-lg transition-shadow">
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-600">{title}</p>
            <p className="text-2xl font-bold text-gray-900">
              ${value.toLocaleString()}
            </p>
            {change && (
              <div
                className={`flex items-center mt-2 text-sm ${
                  trend === "up" ? "text-green-600" : "text-red-600"
                }`}
              >
                {trend === "up" ? (
                  <ArrowUpRight className="w-4 h-4 mr-1" />
                ) : (
                  <ArrowDownRight className="w-4 h-4 mr-1" />
                )}
                {change}% from last month
              </div>
            )}
          </div>
          <div
            className={`p-3 rounded-full ${
              trend === "up"
                ? "bg-green-100"
                : trend === "down"
                  ? "bg-red-100"
                  : "bg-blue-100"
            }`}
          >
            <Icon
              className={`w-6 h-6 ${
                trend === "up"
                  ? "text-green-600"
                  : trend === "down"
                    ? "text-red-600"
                    : "text-blue-600"
              }`}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );

  const InsightCard = ({ insight }) => {
    const getIcon = () => {
      switch (insight.type) {
        case "positive":
          return <CheckCircle className="w-5 h-5 text-green-600" />;
        case "warning":
          return <AlertTriangle className="w-5 h-5 text-yellow-600" />;
        case "reminder":
          return <Clock className="w-5 h-5 text-blue-600" />;
        default:
          return <Brain className="w-5 h-5 text-purple-600" />;
      }
    };

    const getBadgeColor = () => {
      switch (insight.severity) {
        case "warning":
          return "bg-yellow-100 text-yellow-800";
        case "critical":
          return "bg-red-100 text-red-800";
        default:
          return "bg-blue-100 text-blue-800";
      }
    };

    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="p-4 border border-gray-200 rounded-lg hover:shadow-md transition-shadow"
      >
        <div className="flex items-start justify-between">
          <div className="flex items-start space-x-3">
            {getIcon()}
            <div>
              <h4 className="font-medium text-gray-900">{insight.title}</h4>
              <p className="text-sm text-gray-600 mt-1">
                {insight.description}
              </p>
            </div>
          </div>
          <Badge className={getBadgeColor()}>{insight.severity}</Badge>
        </div>
      </motion.div>
    );
  };

  if (dashboardData.loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-32 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Welcome back, {user?.first_name}!
          </h1>
          <p className="text-gray-600 mt-1">
            Here's what's happening with {user?.business_name} today.
          </p>
        </div>
        <Button className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700">
          Generate Report
        </Button>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <MetricCard
          title="Total Revenue"
          value={dashboardData.metrics.totalRevenue}
          change={12}
          trend="up"
          icon={TrendingUp}
        />
        <MetricCard
          title="Total Expenses"
          value={dashboardData.metrics.totalExpenses}
          change={8}
          trend="up"
          icon={TrendingDown}
        />
        <MetricCard
          title="Net Income"
          value={dashboardData.metrics.netIncome}
          change={15}
          trend="up"
          icon={DollarSign}
        />
        <MetricCard
          title="Cash Flow"
          value={dashboardData.metrics.cashFlow}
          change={5}
          trend="up"
          icon={BarChart3}
        />
        <MetricCard
          title="Accounts Receivable"
          value={dashboardData.metrics.accountsReceivable}
          change={3}
          trend="down"
          icon={CreditCard}
        />
        <MetricCard
          title="Accounts Payable"
          value={dashboardData.metrics.accountsPayable}
          change={7}
          trend="down"
          icon={PieChart}
        />
      </div>

      {/* Charts and Insights */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Cash Flow Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Cash Flow Trend</CardTitle>
            <CardDescription>Monthly income vs expenses</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={dashboardData.cashFlowData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip
                  formatter={(value) => [`$${value.toLocaleString()}`, ""]}
                />
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

        {/* Expense Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle>Expense Breakdown</CardTitle>
            <CardDescription>Current month distribution</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <RechartsPieChart>
                <Pie
                  data={dashboardData.expenseBreakdown}
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  dataKey="value"
                  label={({ name, percent }) =>
                    `${name} ${(percent * 100).toFixed(0)}%`
                  }
                >
                  {dashboardData.expenseBreakdown.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value) => [
                    `$${value.toLocaleString()}`,
                    "Amount",
                  ]}
                />
              </RechartsPieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* AI Insights and Recent Transactions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* AI Insights */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Brain className="w-5 h-5 text-purple-600" />
              <span>AI Insights</span>
            </CardTitle>
            <CardDescription>
              Intelligent recommendations for your business
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {dashboardData.insights.map((insight) => (
              <InsightCard key={insight.id} insight={insight} />
            ))}
            <Button variant="outline" className="w-full">
              View All Insights
            </Button>
          </CardContent>
        </Card>

        {/* Recent Transactions */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Transactions</CardTitle>
            <CardDescription>Latest financial activity</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {dashboardData.recentTransactions.map((transaction) => (
                <div
                  key={transaction.id}
                  className="flex items-center justify-between p-3 border border-gray-100 rounded-lg"
                >
                  <div>
                    <p className="font-medium text-gray-900">
                      {transaction.description}
                    </p>
                    <p className="text-sm text-gray-500">{transaction.date}</p>
                  </div>
                  <div
                    className={`font-bold ${
                      transaction.amount > 0 ? "text-green-600" : "text-red-600"
                    }`}
                  >
                    {transaction.amount > 0 ? "+" : ""}$
                    {Math.abs(transaction.amount).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
            <Button variant="outline" className="w-full mt-4">
              View All Transactions
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Dashboard;
