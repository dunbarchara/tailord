import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { Header } from '@/components/Header';
import { HeroSection } from '@/components/home/HeroSection';
import { ProductPreview } from '@/components/home/ProductPreview';
import { HowItWorks } from '@/components/home/HowItWorks';
import { DifferentiatorSection } from '@/components/home/DifferentiatorSection';
import { ClosingCTA } from '@/components/home/ClosingCTA';
import { Footer } from '@/components/Footer';

export default async function Home() {
  const session = await getServerSession(authOptions);
  const isSignedIn = !!session?.user;

  return (
    <main className="min-h-screen">
      <Header />
      <div className="h-14" />
      <HeroSection isSignedIn={isSignedIn} />
      <ProductPreview />
      <HowItWorks />
      <DifferentiatorSection />
      <ClosingCTA isSignedIn={isSignedIn} />
      <Footer />
    </main>
  );
}
