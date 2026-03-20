# NexaFi Web Frontend

Enterprise-grade AI-powered financial management platform frontend built with React, Vite, and Tailwind CSS.

## Features

- **Modern Stack**: React 19, Vite 6, Tailwind CSS 4
- **Authentication**: Secure login/register with JWT tokens
- **Dashboard**: Real-time financial metrics and AI insights
- **Accounting Module**: Chart of accounts, journal entries, financial reports
- **Payments Module**: Multi-currency wallets, transactions, payment analytics
- **AI Insights Module**: Cash flow predictions, credit scoring, AI chat assistant
- **Settings Module**: User profile, security, notifications management
- **Responsive Design**: Mobile-first approach with beautiful UI
- **Comprehensive Testing**: Unit and integration tests with Vitest

## Prerequisites

- Node.js 18+ or npm/pnpm
- Backend services running on `http://localhost:5000` (or configure in `.env`)

## Installation

```bash
# Install dependencies
npm install --legacy-peer-deps

# Or using pnpm (recommended)
pnpm install
```

## Configuration

1. Copy the environment example file:

```bash
cp .env.example .env
```

2. Update `.env` with your configuration:

```env
VITE_API_BASE_URL=http://localhost:5000/api/v1
VITE_API_TIMEOUT=30000
VITE_ENVIRONMENT=development
```

## Development

```bash
# Start development server
npm run dev

# The app will be available at http://localhost:3000
```

## Building for Production

```bash
# Create production build
npm run build

# Preview production build locally
npm run preview
```

## Testing

```bash
# Run all tests
npm test

# Run tests with UI
npm run test:ui

# Run tests with coverage
npm run test:coverage
```

## Project Structure

```
web-frontend/
├── src/
│   ├── components/               # React components
│   │   ├── ui/                   # Reusable UI components (shadcn/ui)
│   │   ├── AccountingModule.jsx
│   │   ├── AIInsightsModule.jsx
│   │   ├── AuthPage.jsx
│   │   ├── Dashboard.jsx
│   │   ├── Homepage.jsx
│   │   ├── Layout.jsx
│   │   ├── PaymentsModule.jsx
│   │   └── SettingsModule.jsx
│   ├── contexts/                 # React contexts (Auth, App)
│   ├── hooks/                    # Custom React hooks
│   ├── lib/                      # Utilities and API client
│   ├── __tests__/                # Test files
│   ├── test/                     # Test configuration
│   ├── App.jsx                   # Main app component
│   ├── App.css                   # App-specific styles
│   ├── index.css                 # Global styles
│   └── main.jsx                  # Entry point
├── public/                       # Static assets
├── .env.example                  # Environment variables example
├── package.json                  # Dependencies and scripts
├── vite.config.js                # Vite configuration
├── vitest.config.js              # Vitest testing configuration
├── eslint.config.js              # ESLint configuration
├── components.json               # shadcn/ui configuration
└── README.md                     # This file
```

## Key Components

### Authentication (AuthPage)

- Login and registration forms
- Form validation with error handling
- JWT token management
- Automatic session persistence

### Dashboard

- Financial metrics overview
- Cash flow trends chart
- Expense breakdown visualization
- AI insights cards
- Recent transactions list

### Accounting Module

- Chart of accounts management
- Journal entries creation
- Financial reports (Trial Balance, Balance Sheet, Income Statement)
- Account filtering and search

### Payments Module

- Payment methods management
- Transaction history
- Multi-currency wallet support
- Payment analytics dashboard

### AI Insights Module

- Cash flow predictions
- Credit score analysis
- AI-powered recommendations
- Interactive chat assistant
- Insight management

### Settings Module

- User profile management
- Security settings (password change, 2FA)
- Notification preferences
- Theme customization
- Business information

## API Integration

The frontend communicates with the backend through a centralized API client (`src/lib/api.js`).

### API Client Features:

- Automatic JWT token handling
- Request/response interceptors
- Error handling and retries
- Timeout support
- TypeScript-friendly

### Example Usage:

```javascript
import apiClient from "./lib/api";

// Login
const { access_token, user } = await apiClient.login({
  email: "user@example.com",
  password: "password123",
});

// Fetch accounts
const { accounts } = await apiClient.getAccounts();

// Create transaction
const transaction = await apiClient.createTransaction({
  amount: 100.0,
  description: "Payment received",
  type: "income",
});
```

## Testing Strategy

### Unit Tests

- Component rendering tests
- API client tests
- Context provider tests
- Utility function tests

### Integration Tests

- User authentication flow
- Data fetching and display
- Form submissions
- Navigation and routing

### Test Coverage

- Current coverage: ~85%
- Goal: 90%+

## Styling

The project uses:

- **Tailwind CSS 4**: Utility-first CSS framework
- **shadcn/ui**: High-quality, accessible React components
- **Framer Motion**: Animation library
- **Recharts**: Data visualization

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Performance

- Code splitting with dynamic imports
- Lazy loading of routes
- Optimized bundle size
- Production build: ~1.1MB (gzipped: ~320KB)

## Security

- JWT token storage in localStorage
- Automatic token refresh
- Protected routes
- XSS protection
- CSRF tokens for mutations

## Troubleshooting

### Common Issues

1. **Dependencies installation fails**

   ```bash
   npm install --legacy-peer-deps
   ```

2. **Build fails with memory error**

   ```bash
   NODE_OPTIONS=--max_old_space_size=4096 npm run build
   ```

3. **API requests fail**
   - Check `.env` configuration
   - Verify backend is running
   - Check CORS settings

4. **Tests fail**
   - Clear node_modules and reinstall
   - Check test setup configuration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write/update tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details
