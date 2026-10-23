"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import { fa, moneyShort } from "@/lib/format";
import type { Store } from "@/lib/types";

/** Leaflet is loaded lazily in the browser; tiles degrade gracefully offline. */
export default function MapView({
  stores,
  center,
  selectedId,
  onSelect,
}: {
  stores: Store[];
  center: { lat: number; lon: number };
  selectedId?: string | null;
  onSelect?: (id: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const markersRef = useRef<Record<string, any>>({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !ref.current) return;

      if (!mapRef.current) {
        mapRef.current = L.map(ref.current, {
          zoomControl: false,
          attributionControl: true,
          scrollWheelZoom: false,
        }).setView([center.lat, center.lon], 13);

        L.tileLayer(
          process.env.NEXT_PUBLIC_MAP_TILE_URL || "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
          {
            maxZoom: 19,
            attribution: "© OpenStreetMap",
            crossOrigin: true,
            errorTileUrl:
              "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNTYiIGhlaWdodD0iMjU2Ij48cmVjdCB3aWR0aD0iMjU2IiBoZWlnaHQ9IjI1NiIgZmlsbD0iI2U4ZWVmNSIvPjwvc3ZnPg==",
          },
        ).addTo(mapRef.current);

        L.circleMarker([center.lat, center.lon], {
          radius: 7,
          color: "#fff",
          weight: 3,
          fillColor: "#1d4ed8",
          fillOpacity: 1,
        }).addTo(mapRef.current);
      } else {
        mapRef.current.setView([center.lat, center.lon], 13);
      }

      // clear old markers
      Object.values(markersRef.current).forEach((m: any) => m.remove());
      markersRef.current = {};

      const bounds: [number, number][] = [];
      stores.forEach((s) => {
        const lat = (s as any).lat ?? null;
        const lon = (s as any).lon ?? null;
        if (lat == null || lon == null) return;
        // stores may not carry lat/lon; fall back to nothing
        const icon = L.divIcon({
          className: "",
          html: `<div class="price-pin ${selectedId === s.shop_id ? "selected" : ""}">${
            s.price_valid && s.price != null ? moneyShort(s.price) : "نامشخص"
          }</div>`,
          iconSize: [64, 24],
          iconAnchor: [32, 12],
        });
        const m = L.marker([lat, lon], { icon })
          .addTo(mapRef.current)
          .on("click", () => onSelect?.(s.shop_id));
        m.bindPopup(
          `<b>${s.name}</b><br/>${s.location_label || ""}<br/>${
            s.price_valid && s.price != null ? moneyShort(s.price) + " تومان" : "قیمت نامشخص"
          }<br/><span style="color:#5a6884">${fa(s.travel_minutes)} دقیقه</span>`,
        );
        markersRef.current[s.shop_id] = m;
        bounds.push([lat, lon]);
      });
      if (bounds.length > 1) {
        mapRef.current.fitBounds(bounds, { padding: [30, 30], maxZoom: 14 });
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stores, center.lat, center.lon, selectedId]);

  useEffect(() => {
    return () => {
      mapRef.current?.remove?.();
      mapRef.current = null;
    };
  }, []);

  return <div ref={ref} className="h-[280px] w-full overflow-hidden rounded-xl2 border border-slate-200" />;
}
