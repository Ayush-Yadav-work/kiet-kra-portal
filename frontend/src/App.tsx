import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import ChangePassword from './auth/ChangePassword'
import LoginPage, { Landing } from './auth/LoginPage'
import { RequireRole } from './components/ui'
import { DeanInbox, DeanNotice } from './features/announcements/DeanAnnouncements'
import { VCAnnouncementEditor, VCAnnouncementList } from './features/announcements/VCAnnouncements'
import DeanDashboard from './features/dean/DeanDashboard'
import WorkspaceRoute from './features/report-builder/Workspace'
import AdminAssignments from './features/vc/AdminAssignments'
import AdminKRAs from './features/vc/AdminKRAs'
import Analytics from './features/vc/Analytics'
import ReopenQueue from './features/vc/ReopenQueue'
import ReviewPage from './features/vc/ReviewPage'
import VCDashboard from './features/vc/VCDashboard'

const router = createBrowserRouter([
  { path: '/', element: <Landing /> },
  { path: '/dean/login', element: <LoginPage role="DEAN" /> },
  { path: '/vc/login', element: <LoginPage role="VC" /> },
  { path: '/change-password', element: <ChangePassword /> },
  {
    path: '/dean', element: <RequireRole role="DEAN" />, children: [
      { path: 'dashboard', element: <DeanDashboard /> },
      { path: 'kra/:assignmentId/:periodId', element: <WorkspaceRoute /> },
      { path: 'announcements', element: <DeanInbox /> },
      { path: 'announcements/:id', element: <DeanNotice /> },
      { index: true, element: <Navigate to="dashboard" replace /> },
    ],
  },
  {
    path: '/vc', element: <RequireRole role="VC" />, children: [
      { path: 'dashboard', element: <VCDashboard /> },
      { path: 'review/:submissionId', element: <ReviewPage /> },
      { path: 'reopen-requests', element: <ReopenQueue /> },
      { path: 'assignments', element: <AdminAssignments /> },
      { path: 'analytics', element: <Analytics /> },
      { path: 'kras', element: <AdminKRAs /> },
      { path: 'announcements', element: <VCAnnouncementList /> },
      { path: 'announcements/:id', element: <VCAnnouncementEditor /> },
      { index: true, element: <Navigate to="dashboard" replace /> },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])

export default function App() {
  return <AuthProvider><RouterProvider router={router} /></AuthProvider>
}
