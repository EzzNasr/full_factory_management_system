import { useLocation } from "wouter";

const STEPS = [
  { path: "/customers", label: "Customer" },
  { path: "/products", label: "Products" },
  { path: "/quantities", label: "Quantities" },
  { path: "/summary", label: "Summary" },
];

export default function InvoiceStepper() {
  const [, setLocation] = useLocation();
  const [location] = useLocation();

  const currentIndex = STEPS.findIndex(s => s.path === location);

  return (
    <div className="max-w-2xl mx-auto pt-6 px-4">
      <div className="flex items-center justify-center">
        {STEPS.map((step, idx) => (
          <div key={step.path} className="flex items-center">
            <button
              onClick={() => setLocation(step.path)}
              title={step.label}
              className={`w-9 h-9 rounded-full flex items-center justify-center font-bold text-sm border-2 transition-colors ${
                idx === currentIndex
                  ? "bg-blue-600 text-white border-blue-600"
                  : idx < currentIndex
                  ? "bg-blue-100 text-blue-600 border-blue-400"
                  : "bg-background text-muted-foreground border-muted"
              }`}
            >
              {idx + 1}
            </button>
            {idx < STEPS.length - 1 && (
              <div className={`w-12 h-0.5 ${idx < currentIndex ? "bg-blue-400" : "bg-muted"}`} />
            )}
          </div>
        ))}
      </div>
      <div className="flex justify-center gap-1 mt-2 text-xs text-muted-foreground">
        {STEPS.map((step, idx) => (
          <span key={step.path} className={`text-center ${idx === currentIndex ? "font-semibold text-foreground" : ""}`} style={{ width: 56 }}>
            {step.label}
          </span>
        ))}
      </div>
    </div>
  );
}