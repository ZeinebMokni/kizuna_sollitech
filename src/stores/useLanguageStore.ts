import { create } from 'zustand';
import { Language } from '@/types';

interface LanguageState {
  language: Language;
  direction: 'ltr' | 'rtl';
  setLanguage: (lang: Language) => void;
  t: (key: string) => string;
}

const translations: Record<Language, Record<string, string>> = {
  fr: {
    // Brand & Navigation
    'brand.name': 'QATRA',
    'brand.tagline': 'L\'Intelligence pour Chaque Goutte',
    'nav.dashboard': 'Tableau de bord',
    'nav.farm': 'Mon Exploitation',
    'nav.my_lands': 'Mes Terres',
    'nav.digital_twin': 'Jumeau Numérique (Map)',
    'nav.devices': 'Appareils IoT & ESP32',
    'nav.irrigation': 'Gestion de l\'Irrigation',
    'nav.energy': 'Énergie & Solaire',
    'nav.intelligence': 'Intelligence Nationale',
    'nav.forecast': 'Prévisions & Marché',
    'nav.planning': 'Planification IA Cultures',
    'nav.analytics': 'Analyses & Rendements',
    'nav.marketplace': 'Place de Marché',
    'nav.my_listings': 'Mes Récoltes',
    'nav.notifications': 'Alertes & Notifications',
    'nav.settings': 'Paramètres',
    'nav.logout': 'Déconnexion',

    // Dashboard metrics
    'metric.total_area': 'Superficie Totale',
    'metric.active_zones': 'Parcelles Actives',
    'metric.online_devices': 'Capteurs Connectés',
    'metric.daily_water': 'Consommation Eau (Aujourd\'hui)',
    'metric.solar_production': 'Production Solaire',
    'metric.critical_alerts': 'Alertes Requérant Action',
    'metric.battery_level': 'Niveau Batterie',

    // Map Layers
    'layer.health': 'Santé Végétale',
    'layer.moisture': 'Humidité du Sol',
    'layer.temperature': 'Température Sol / Canopée',
    'layer.irrigation': 'Activité d\'Irrigation',
    'layer.energy': 'Empreinte Énergétique',
    'layer.prediction': 'Prédiction Risques',
    'layer.crop': 'Types de Cultures',

    // Common actions
    'action.inspect': 'Inspecter la Parcelle',
    'action.irrigate_now': 'Déclencher Irrigation',
    'action.stop': 'Arrêter',
    'action.emergency_stop': 'ARRÊT D\'URGENCE',
    'action.simulate_outage': 'Simuler Coupure Réseau STEG',
    'action.export_csv': 'Exporter CSV',
    'action.compare': 'Comparer',
    'action.create_listing': 'Mettre en Vente ma Récolte',
    'action.save': 'Enregistrer',

    // Status
    'status.healthy': 'Conditions Optimales',
    'status.warning': 'Vigilance Recommandée',
    'status.critical': 'Stress Critique',
    'status.irrigating': 'Irrigation en cours',
    'status.simulated': 'Données Démonstration Simulées',
  },
  ar: {
    // Brand & Navigation
    'brand.name': 'قطرة',
    'brand.tagline': 'الذكاء لكل قطرة ماء',
    'nav.dashboard': 'لوحة القيادة',
    'nav.farm': 'مزرعتي',
    'nav.my_lands': 'أراضيّ',
    'nav.digital_twin': 'التوأم الرقمي (الخريطة)',
    'nav.devices': 'أجهزة إنترنت الأشياء (ESP32)',
    'nav.irrigation': 'التحكم في الري الذكي',
    'nav.energy': 'الطاقة والطاقة الشمسية',
    'nav.intelligence': 'الاستخبارات الزراعية الوطنية',
    'nav.forecast': 'توقعات السوق والأسعار',
    'nav.planning': 'تخطيط المحاصيل بالذكاء الاصطناعي',
    'nav.analytics': 'التحليلات والمردودية',
    'nav.marketplace': 'سوق المحاصيل',
    'nav.my_listings': 'محاصيلي المعروضة',
    'nav.notifications': 'التنبيهات والإشعارات',
    'nav.settings': 'الإعدادات',
    'nav.logout': 'تسجيل الخروج',

    // Dashboard metrics
    'metric.total_area': 'المساحة الإجمالية',
    'metric.active_zones': 'القطع الفلاحية النشطة',
    'metric.online_devices': 'المستشعرات المتصلة',
    'metric.daily_water': 'استهلاك المياه (اليوم)',
    'metric.solar_production': 'إنتاج الطاقة الشمسية',
    'metric.critical_alerts': 'تنبيهات تتطلب تدخلاً',
    'metric.battery_level': 'مستوى شحن البطارية',

    // Map Layers
    'layer.health': 'صحة النباتات',
    'layer.moisture': 'رطوبة التربة',
    'layer.temperature': 'درجة الحرارة',
    'layer.irrigation': 'حالة الري',
    'layer.energy': 'استهلاك الطاقة',
    'layer.prediction': 'توقع المخاطر',
    'layer.crop': 'نوع المحصول',

    // Common actions
    'action.inspect': 'فحص القطعة',
    'action.irrigate_now': 'تشغيل الري الفوري',
    'action.stop': 'إيقاف',
    'action.emergency_stop': 'إيقاف طوارئ فوري',
    'action.simulate_outage': 'محاكاة انقطاع الكهرباء (الستاغ)',
    'action.export_csv': 'تصدير البيانات CSV',
    'action.compare': 'مقارنة',
    'action.create_listing': 'عرض محصول للبيع',
    'action.save': 'حفظ',

    // Status
    'status.healthy': 'حالة ممتازة',
    'status.warning': 'تحت المراقبة',
    'status.critical': 'إجهاد مائي حرج',
    'status.irrigating': 'الري قيد التشغيل',
    'status.simulated': 'بيانات محاكاة توضيحية',
  },
  en: {
    // Brand & Navigation
    'brand.name': 'QATRA',
    'brand.tagline': 'Intelligence for Every Drop',
    'nav.dashboard': 'Command Center',
    'nav.farm': 'My Farm',
    'nav.my_lands': 'My Lands',
    'nav.digital_twin': 'Digital Twin (Map)',
    'nav.devices': 'IoT Devices & ESP32',
    'nav.irrigation': 'Smart Irrigation',
    'nav.energy': 'Energy & Solar',
    'nav.intelligence': 'National Intelligence',
    'nav.forecast': 'Market Predictions',
    'nav.planning': 'AI Crop Planning',
    'nav.analytics': 'Farm Analytics',
    'nav.marketplace': 'Agricultural Marketplace',
    'nav.my_listings': 'My Harvest Listings',
    'nav.notifications': 'Alerts & Notifications',
    'nav.settings': 'Settings',
    'nav.logout': 'Sign Out',

    // Dashboard metrics
    'metric.total_area': 'Total Area',
    'metric.active_zones': 'Active Zones',
    'metric.online_devices': 'Connected Devices',
    'metric.daily_water': 'Water Used (Today)',
    'metric.solar_production': 'Solar Power',
    'metric.critical_alerts': 'Critical Alerts',
    'metric.battery_level': 'Battery Storage',

    // Map Layers
    'layer.health': 'Vegetation Health',
    'layer.moisture': 'Soil Moisture',
    'layer.temperature': 'Soil / Air Temperature',
    'layer.irrigation': 'Irrigation Activity',
    'layer.energy': 'Energy Footprint',
    'layer.prediction': 'Risk Forecast',
    'layer.crop': 'Crop Varieties',

    // Common actions
    'action.inspect': 'Inspect Zone',
    'action.irrigate_now': 'Start Irrigation',
    'action.stop': 'Stop',
    'action.emergency_stop': 'EMERGENCY SHUTOFF',
    'action.simulate_outage': 'Simulate Grid Blackout',
    'action.export_csv': 'Export CSV',
    'action.compare': 'Compare',
    'action.create_listing': 'List Harvest for Sale',
    'action.save': 'Save',

    // Status
    'status.healthy': 'Optimal Conditions',
    'status.warning': 'Watchlist Advisory',
    'status.critical': 'Critical Water Stress',
    'status.irrigating': 'Actively Irrigating',
    'status.simulated': 'Demonstration Simulated Data',
  },
};

export const useLanguageStore = create<LanguageState>((set, get) => ({
  language: 'fr',
  direction: 'ltr',
  setLanguage: (lang: Language) => {
    set({
      language: lang,
      direction: lang === 'ar' ? 'rtl' : 'ltr',
    });
    if (typeof document !== 'undefined') {
      document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
      document.documentElement.lang = lang;
    }
  },
  t: (key: string) => {
    const currentLang = get().language;
    return translations[currentLang]?.[key] || translations.fr[key] || key;
  },
}));
