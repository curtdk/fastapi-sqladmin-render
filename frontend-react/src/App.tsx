import { useState, useEffect } from 'react'
import './App.css'

interface ApiResponse {
  message: string
  version?: string
  docs?: string
  admin?: string
}

function App() {
  const [apiData, setApiData] = useState<ApiResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // 页面加载时调用后端API
    fetch('http://f.tatagogo.com/')
      .then(res => res.json())
      .then(data => {
        setApiData(data)
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* 顶部导航 */}
      <header className="bg-black/30 backdrop-blur-md border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-white">
            OpenClaw Token 销售
          </h1>
          <nav className="flex gap-6">
            <a href="#" className="text-white/70 hover:text-white transition-colors">首页</a>
            <a href="#" className="text-white/70 hover:text-white transition-colors">关于</a>
            <a href="#" className="text-white/70 hover:text-white transition-colors">联系</a>
          </nav>
        </div>
      </header>

      {/* 主内容区 */}
      <main className="max-w-4xl mx-auto px-4 py-16">
        <div className="text-center mb-12">
          <h2 className="text-5xl font-bold text-white mb-4">
            OpenClaw Token
          </h2>
          <p className="text-xl text-white/70">
            下一代AI助手代币 - 开启智能新时代
          </p>
        </div>

        {/* Token宣传图片 */}
        <div className="flex justify-center mb-12">
          <div className="bg-white/5 backdrop-blur-sm rounded-2xl shadow-2xl border border-white/10 p-4 max-w-2xl">
            <img
              src="/assets/token-sale.svg"
              alt="Token Sale"
              className="w-full h-auto rounded-xl"
              onError={(e) => {
                // 如果图片加载失败，显示占位符
                const target = e.target as HTMLImageElement
                target.style.display = 'none'
                const parent = target.parentElement
                if (parent) {
                  parent.innerHTML = `
                    <div class="flex items-center justify-center h-64 bg-gradient-to-r from-purple-600 to-blue-600 rounded-xl">
                      <span class="text-white text-2xl font-bold">OpenClaw Token Sale</span>
                    </div>
                  `
                }
              }}
            />
          </div>
        </div>

        {/* API测试结果 */}
        <div className="bg-black/30 backdrop-blur-sm rounded-xl border border-white/10 p-6 max-w-xl mx-auto">
          <h3 className="text-xl font-semibold text-white mb-4">
            🔗 后端API连接测试
          </h3>
          
          {loading && (
            <div className="text-white/50">正在连接后端...</div>
          )}

          {error && (
            <div className="text-red-400 bg-red-500/10 p-3 rounded-lg">
              ❌ 连接失败: {error}
            </div>
          )}

          {apiData && !loading && (
            <div className="text-left">
              <div className="bg-green-500/10 border border-green-500/30 p-3 rounded-lg mb-3">
                ✅ 连接成功!
              </div>
              <div className="space-y-2 text-white/80 font-mono text-sm">
                <p><span className="text-purple-400">message:</span> {apiData.message}</p>
                <p><span className="text-purple-400">version:</span> {apiData.version}</p>
                <p><span className="text-purple-400">docs:</span> {apiData.docs}</p>
                <p><span className="text-purple-400">admin:</span> {apiData.admin}</p>
              </div>
            </div>
          )}
        </div>

        {/* 按钮 */}
        <div className="text-center mt-12">
          <button className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white font-semibold py-3 px-8 rounded-full transition-all transform hover:scale-105 shadow-lg">
            立即购买 Token
          </button>
        </div>
      </main>

      {/* 底部 */}
      <footer className="bg-black/30 border-t border-white/10 py-6">
        <div className="max-w-7xl mx-auto px-4 text-center text-white/50">
          © 2026 OpenClaw Token. All rights reserved.
        </div>
      </footer>
    </div>
  )
}

export default App
