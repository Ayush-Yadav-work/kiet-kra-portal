import { createBrowserRouter, Link, Navigate, RouterProvider } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import ChangePassword from './auth/ChangePassword'
import LoginPage from './auth/LoginPage'
import { RequireRole } from './components/ui'
import DeanDashboard from './features/dean/DeanDashboard'
import WorkspaceRoute from './features/report-builder/Workspace'
import ReopenQueue from './features/vc/ReopenQueue'
import ReviewPage from './features/vc/ReviewPage'
import VCDashboard from './features/vc/VCDashboard'

function Landing() {
  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-lg space-y-4 text-center">
        <h1 className="text-2xl font-semibold text-blue-900">KIET KRA Portal</h1>
        <p className="text-sm text-slate-600">Bimonthly KRA reporting for KIET Deemed to be University.</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Link to="/dean/login" className="card hover:border-blue-500"><p className="font-semibold">Dean login</p><p className="text-xs text-slate-600">Department reports and evidence</p></Link>
          <Link to="/vc/login" className="card hover:border-blue-500"><p className="font-semibold">Vice Chancellor login</p><p className="text-xs text-slate-600">Review, approval and reopening</p></Link>
        </div>
      </div>
    </main>
  )
}

const router = createBrowserRouter([
  { path: '/', element: <Landing /> },
  { path: '/dean/login', element: <LoginPage role="DEAN" /> },
  { path: '/vc/login', element: <LoginPage role="VC" /> },
  { path: '/change-password', element: <ChangePassword /> },
  {
    path: '/dean', element: <RequireRole role="DEAN" />, children: [
      { path: 'dashboard', element: <DeanDashboard /> },
      { path: 'kra/:assignmentId/:periodId', element: <WorkspaceRoute /> },
      { index: true, element: <Navigate to="dashboard" replace /> },
    ],
  },
  {
    path: '/vc', element: <RequireRole role="VC" />, children: [
      { path: 'dashboard', element: <VCDashboard /> },
      { path: 'review/:submissionId', element: <ReviewPage /> },
      { path: 'reopen-requests', element: <ReopenQueue /> },
      { index: true, element: <Navigate to="dashboard" replace /> },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])

export default function App() {
  return <AuthProvider><RouterProvider router={router} /></AuthProvider>
}
