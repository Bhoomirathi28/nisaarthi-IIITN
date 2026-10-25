import { useT } from "../i18n";
import { IconHelp, IconHome, IconPeople, IconRoute } from "./Icons";

const TABS = [
  { id: "home", key: "nav_home", Icon: IconHome },
  { id: "plan", key: "nav_plan", Icon: IconRoute },
  { id: "help", key: "nav_help", Icon: IconHelp },
  { id: "contacts", key: "nav_contacts", Icon: IconPeople },
];

export default function BottomNav({ tab, setTab }) {
  const { t } = useT();
  return (
    <nav className="bottom-nav">
      {TABS.map(({ id, key, Icon }) => (
        <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}
          aria-current={tab === id ? "page" : undefined}>
          <Icon />
          <span>{t(key)}</span>
        </button>
      ))}
    </nav>
  );
}
