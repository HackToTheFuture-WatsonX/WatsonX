import { useEffect } from 'react'
import { HashRouter, Routes, Route } from 'react-router-dom'
import Sidebar      from './components/Sidebar'
import ChatBubble   from './components/ChatBubble'
import ToastHost    from './components/ui/Toast'
import Home         from './pages/Home'
import Sync         from './pages/Sync'
import Scan         from './pages/Scan'
import Extract      from './pages/Extract'
import View         from './pages/View'
import Insights     from './pages/Insights'
import Settings     from './pages/Settings'
import { useChatStore } from './store/chat'

export default function App() {
  const hydrate = useChatStore((s) => s.hydrate)

  useEffect(() => { hydrate() }, [hydrate])

  return (
    <HashRouter>
      <div className="flex h-screen overflow-hidden bg-bg-light dark:bg-bg-dark">
        <Sidebar />
        <div className="flex flex-col flex-1 min-w-0">
          {/* Main content — responsive to window size */}
          <main className="flex-1 overflow-y-auto overflow-x-hidden w-full">
            <Routes>
              <Route path="/"         element={<Home />} />
              <Route path="/sync"     element={<Sync />} />
              <Route path="/scan"     element={<Scan />} />
              <Route path="/extract"  element={<Extract />} />
              <Route path="/view"     element={<View />} />
              <Route path="/insights" element={<Insights />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </main>
        </div>

        {/* Global floating assistant + toast overlay */}
        <ChatBubble />
        <ToastHost />
      </div>
    </HashRouter>
  )
}
