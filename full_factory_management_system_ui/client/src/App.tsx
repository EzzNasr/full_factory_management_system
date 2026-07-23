import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/NotFound";
import { Route, Switch } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";
import DashboardLayout from "./components/DashboardLayout";
import CustomerSelection from "./pages/CustomerSelection";
import ProductSelection from "./pages/ProductSelection";
import QuantityInput from "./pages/QuantityInput";
import Summary from "./pages/Summary";
import OrderViewer from "./pages/OrderViewer";
import OrdersList from "./pages/OrdersList";
import Dashboard from "./pages/Dashboard";
import ProductsManager from "./pages/ProductsManager";
import CustomerBalances from "./pages/CustomerBalances";
import Expenses from "./pages/Expenses";
import Workers from "./pages/Workers";
import { InvoiceProvider } from "./contexts/InvoiceContext";

function Router() {
  return (
    <Switch>
      <Route path={"/"} component={CustomerSelection} />
      <Route path={"/customers"} component={CustomerSelection} />
      <Route path={"/products"} component={ProductSelection} />
      <Route path={"/quantities"} component={QuantityInput} />
      <Route path={"/summary"} component={Summary} />
      <Route path={"/orders"} component={OrdersList} />
      <Route path={"/orders/:id"} component={OrderViewer} />
      <Route path={"/dashboard"} component={Dashboard} />
      <Route path={"/products-manager"} component={ProductsManager} />
      <Route path={"/customer-balances"} component={CustomerBalances} />
      <Route path={"/expenses"} component={Expenses} />
      <Route path={"/workers"} component={Workers} />
      <Route path={"/404"} component={NotFound} />
      {/* Final fallback route */}
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider defaultTheme="light">
        <InvoiceProvider>
          <TooltipProvider>
            <Toaster />
            <DashboardLayout>
              <Router />
            </DashboardLayout>
          </TooltipProvider>
        </InvoiceProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;