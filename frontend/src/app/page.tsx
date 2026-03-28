import { Header } from '@/components/Header';
import { HeroSection } from '@/components/home/HeroSection';
import { ProductPreview } from '@/components/home/ProductPreview';
import { HowItWorks } from '@/components/home/HowItWorks';
import { DifferentiatorSection } from '@/components/home/DifferentiatorSection';
import { ClosingCTA } from '@/components/home/ClosingCTA';
import { Footer } from '@/components/Footer';

export default function Home() {
  return (
    <main className="min-h-screen">
      <Header />
      <HeroSection />
      <ProductPreview />
      <HowItWorks />
      <DifferentiatorSection />
      <ClosingCTA />
      <Footer />
    </main>
  );
}
