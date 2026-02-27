import { Header } from '@/components/Header';
import { Hero } from '@/components/Hero';
import { FeaturesTailord } from '@/components/FeaturesTailord';
import { Footer } from '@/components/Footer';

export default function Home() {
  return (
    <main className="min-h-screen">
      <Header />
      <Hero />
      <FeaturesTailord />
      <Footer />
    </main>
  );
}
