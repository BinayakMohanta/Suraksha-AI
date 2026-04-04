import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";

async function bootstrap() {
	try {
		const response = await fetch("/api/public-config", { headers: { Accept: "application/json" } });
		if (response.ok) {
			const config = await response.json();
			window.__APP_CONFIG__ = {
				supabaseUrl: config?.supabaseUrl,
				supabasePublishableKey: config?.supabasePublishableKey,
			};
		}
	} catch {
		// Ignore bootstrap failures; env-based config may still be available.
	}

	createRoot(document.getElementById("root")!).render(<App />);
}

bootstrap();
