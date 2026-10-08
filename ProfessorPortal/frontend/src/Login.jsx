import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import toast, { Toaster } from 'react-hot-toast';

function Login() {
  const [email, setEmail] = useState('professor@csumb.edu');
  const [password, setPassword] = useState('password123');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    
    const loadingToast = toast.loading('Authenticating...', { style: { background: '#3f3f46', color: '#fff' }});

    try {
      const response = await fetch('http://localhost:8080/api/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Login failed');
      }

      // Securely store the token and professor name
      localStorage.setItem('prof_token', data.access_token);
      localStorage.setItem('prof_name', data.name);
      
      toast.success('Login Successful!', { id: loadingToast, style: { background: '#3f3f46', color: '#fff' } });
      
      // Redirect to the dashboard
      navigate('/dashboard');

    } catch (error) {
      console.error('Login Error:', error);
      toast.error(error.message, { id: loadingToast, style: { background: '#3f3f46', color: '#fff' } });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4 selection:bg-blue-500/30">
      <Toaster position="bottom-right" />
      
      <motion.div 
        initial={{ opacity: 0, y: 20 }} 
        animate={{ opacity: 1, y: 0 }} 
        className="w-full max-w-md"
      >
        <div className="text-center mb-10">
          <h1 className="text-4xl font-black tracking-wider text-zinc-100 mb-2">
            Course<span className="text-blue-500">Eval</span>
          </h1>
          <p className="text-zinc-500 font-medium tracking-wide uppercase text-sm">Faculty Portal</p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 p-8 rounded-2xl shadow-2xl">
          <h2 className="text-2xl font-bold text-zinc-100 mb-6">Welcome back</h2>
          
          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="block text-sm font-bold text-zinc-400 mb-2 uppercase tracking-wide">Institutional Email</label>
              <input 
                type="email" 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-zinc-100 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-bold text-zinc-400 mb-2 uppercase tracking-wide">Password</label>
              <input 
                type="password" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-zinc-100 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                required
              />
            </div>

            <button 
              type="submit" 
              disabled={isLoading}
              className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3.5 rounded-lg transition-all shadow-lg hover:shadow-blue-500/25 mt-4 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Signing in...' : 'Sign In to Portal'}
            </button>
          </form>
          
          <div className="mt-8 pt-6 border-t border-zinc-800 text-center">
            <p className="text-xs text-zinc-600 font-medium">
              Secure access restricted to authorized faculty and staff.
            </p>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

export default Login;