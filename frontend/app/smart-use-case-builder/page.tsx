import { redirect } from 'next/navigation'

export default function SmartUseCaseBuilderPage() {
  // Redirect to use-cases page with smart builder tab
  redirect('/use-cases#builder')
}