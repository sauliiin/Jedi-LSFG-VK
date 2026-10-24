import { staticClasses } from "@decky/ui";
import { definePlugin } from "@decky/api";
import { GiPlasticDuck } from "react-icons/gi";
import { Content } from "./components/Content";
import { notifyPluginUpdate } from "./utils/pluginUpdate";

export default definePlugin(() => {
  console.log("Jedi LSFG-VK plugin initializing");
  void notifyPluginUpdate();

  return {
    name: "Jedi LSFG-VK",
    titleView: <div className={staticClasses.Title}>Jedi LSFG-VK</div>,
    alwaysRender: true,
    content: <Content />,
    icon: <GiPlasticDuck />,
    onDismount() {
      console.log("Jedi LSFG-VK unloading");
    }
  };
});
