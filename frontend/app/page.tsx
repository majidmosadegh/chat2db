import { redirect } from 'next/navigation'

export default function HomePage() {
  // Redirect to the first module (model settings)
  redirect('/models')
}
