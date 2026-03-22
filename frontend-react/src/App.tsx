import { useState } from 'react'
import './App.css'
import { Button } from './components/ui/button'
import { RefreshCw, CheckCircle, XCircle, Plug } from 'lucide-react'

interface ApiResponse {
  message: string
  version?: string
  docs?: string
  admin?: string
}

function App() {
  const [apiData, setApiData] = useState<ApiResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 测试API接口
  const testApi = () => {
    setLoading(true)
    setError(null)
    setApiData(null)
    
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
  }

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
            />
          </div>
        </div>

        {/* API测试区域 */}
        <div className="bg-black/30 backdrop-blur-sm rounded-xl border border-white/10 p-6 max-w-xl mx-auto mb-8">
          <h3 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <Plug className="w-5 h-5" />
            后端API连接测试
          </h3>
          
          {/* 测试按钮 */}
          <div className="flex justify-center mb-4">
            <Button 
              onClick={testApi}
              variant="gradient"
              size="lg"
              disabled={loading}
              className="flex items-center gap-2"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  测试中...
                </>
              ) : (
                <>
                  <Plug className="w-5 h-5" />
                  点击测试 FastAPI 接口
                </>
              )}
            </Button>
          </div>

          {/* API返回结果 */}
          {loading && (
            <div className="text-white/50 flex items-center justify-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin" />
              正在连接后端...
            </div>
          )}

          {error && (
            <div className="text-red-400 bg-red-500/10 p-3 rounded-lg flex items-center gap-2">
              <XCircle className="w-5 h-5" />
              <span>连接失败: {error}</span>
            </div>
          )}

          {apiData && !loading && (
            <div className="text-left">
              <div className="bg-green-500/10 border border-green-500/30 p-3 rounded-lg mb-3 flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-green-400" />
                <span className="text-green-400 font-semibold">连接成功!</span>
              </div>
              <div className="space-y-2 text-white/80 font-mono text-sm bg-black/20 p-4 rounded-lg">
                <p><span className="text-purple-400">message:</span> {apiData.message}</p>
                <p><span className="text-purple-400">version:</span> {apiData.version}</p>
                <p><span className="text-purple-400">docs:</span> {apiData.docs}</p>
                <p><span className="text-purple-400">admin:</span> {apiData.admin}</p>
              </div>
            </div>
          )}

          {/* 提示信息 */}
          {!apiData && !loading && !error && (
            <div className="text-white/50 text-center text-sm">
              点击上方按钮测试后端API连接
            </div>
          )}
        </div>

        {/* 购买按钮 */}
        <div className="text-center">
          <Button variant="gradient" size="lg" className="flex items-center gap-2 mx-auto">
            立即购买 Token
          </Button>
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
