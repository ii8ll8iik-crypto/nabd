export type Lang = "en" | "ar";

export const ZONE_LABELS: Record<string, { en: string; ar: string; color: string }> = {
  female_student_housing: { en: "Female Student Housing", ar: "سكن طالبات", color: "#ec4899" },
  male_student_housing: { en: "Male Student Housing", ar: "سكن طلاب شباب", color: "#38bdf8" },
  family_neighborhood: { en: "Family Neighborhood", ar: "حي عائلات", color: "#10b981" },
  youth_commercial_hub: { en: "Youth Commercial Hub", ar: "مركز شبابي تجاري", color: "#f59e0b" },
  senior_quiet_district: { en: "Quiet / Senior District", ar: "حي هادئ / كبار سن", color: "#a855f7" },
};

export const AXIS_LABELS_I18N: Record<string, { en: string; ar: string }> = {
  students: { en: "Students", ar: "طلاب" },
  youth_male: { en: "Young Men", ar: "شباب (ذكور)" },
  youth_female: { en: "Young Women", ar: "شابات (إناث)" },
  families: { en: "Families", ar: "عائلات" },
  seniors: { en: "Seniors", ar: "كبار سن" },
  commuters: { en: "Commuters", ar: "عابرو طريق" },
};

export const TIME_LABELS_I18N: Record<string, { en: string; ar: string }> = {
  morning: { en: "Morning", ar: "صباحاً" },
  midday: { en: "Midday", ar: "ظهراً" },
  evening: { en: "Evening", ar: "مساءً" },
  night: { en: "Night", ar: "ليلاً" },
};

export const TOOL_HINTS_I18N: Record<Lang, Record<string, string>> = {
  en: {
    inject: "Inject Mode: Click any street or drag the glowing cyan beacon to scrub metrics live",
    paint: "Reality Brush: Click any district to recolor its 3D buildings & update local demographics",
    close_road: "Close Road: Click any junction to sever it and watch pedestrians reroute live",
    demolish: "Demolish Block: Click any building to flatten it & remove its population (click again to restore)",
    add_pop: "Population Surge: Click anywhere to drop +1,500 new residents and see demand shift",
  },
  ar: {
    inject: "وضع الزرع: انقر أي شارع أو اسحب المؤشر السماوي المضيء لتحريك الموقع بدقة",
    paint: "فرشاة السكان: انقر فوق أي حي لتلوين مبانيه وتغيير تركيبته الديموغرافية فوراً",
    close_road: "إغلاق طريق: انقر على أي تقاطع لإغلاقه ومشاهدة إعادة توجيه المشاة والعزلة الجديدة",
    demolish: "هدم مبنى: انقر على أي مبنى لهدمه وحذف كتلته السكانية (انقر مجدداً للاستعادة)",
    add_pop: "إضافة سكان: انقر على أي أرض لإسقاط تجمع سكاني جديد (+1,500 ساكن) ومشاهدة تغيّر الطلب",
  },
};

export const QUICK_CITIES = [
  { nameEn: "Manhattan, NY", nameAr: "مانهاتن، نيويورك", lat: 40.758, lon: -73.9855, zoom: 15.2 },
  { nameEn: "London, Soho", nameAr: "لندن، سوهو", lat: 51.5136, lon: -0.1365, zoom: 15.3 },
  { nameEn: "Tokyo, Shibuya", nameAr: "طوكيو، شيبويا", lat: 35.6595, lon: 139.7004, zoom: 15.3 },
  { nameEn: "Amman, Abdali", nameAr: "عمّان، العبدلي", lat: 31.9632, lon: 35.9078, zoom: 15.2 },
  { nameEn: "Irbid, Yarmouk", nameAr: "إربد، اليرموك", lat: 32.5365, lon: 35.8555, zoom: 15.2 },
];
