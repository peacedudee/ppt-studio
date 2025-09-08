import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppLayout } from './components/AppLayout';
import HomePage from './pages/HomePage'; // <-- Import the new page
import EnhancerPage from './pages/EnhancerPage';
import CreatorPage from './pages/CreatorPage';
import FeedbackPage from './pages/FeedbackPage';

function App() {
  return (
    <BrowserRouter>
      <AppLayout>
        <Routes>
          <Route path="/" element={<HomePage />} /> {/* <-- Use the new component */}
          <Route path="/enhancer" element={<EnhancerPage />} />
          <Route path="/creator" element={<CreatorPage />} />
          <Route path="/feedback" element={<FeedbackPage />} /> {/* <-- Add the new route */}
        </Routes>
      </AppLayout>
    </BrowserRouter>
  );
}

export default App;