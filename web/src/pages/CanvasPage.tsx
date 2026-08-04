import { useState } from "react";
import BrandBar from "@/components/BrandBar";
import GalleryDrawer from "@/components/GalleryDrawer";
import InfiniteCanvas from "@/components/InfiniteCanvas";

export default function CanvasPage() {
  const [galleryOpen, setGalleryOpen] = useState(false);

  const handleReset = () => {
    window.location.reload();
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-charcoal-900 text-ivory-500 overflow-hidden">
      <BrandBar onReset={handleReset} onOpenGallery={() => setGalleryOpen(true)} />
      <InfiniteCanvas />
      <GalleryDrawer open={galleryOpen} onClose={() => setGalleryOpen(false)} />
    </div>
  );
}
