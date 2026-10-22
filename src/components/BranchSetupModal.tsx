import { DialogButton, ModalRoot, showModal } from "@decky/ui";

export function showBranchSetupModal() {
  let closeModal = () => {};
  const modal = showModal(
    <ModalRoot
      bAllowFullSize
      closeModal={() => closeModal()}
      onCancel={() => closeModal()}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "900px",
          boxSizing: "border-box",
          maxHeight: "calc(100vh - 120px)",
          overflowY: "auto",
          padding: "8px 16px 16px",
          margin: "0 auto",
        }}
      >
        <div style={{ fontSize: "20px", fontWeight: 600, marginBottom: "8px" }}>
          Lossless.dll was not found
        </div>
        <div style={{ lineHeight: 1.5 }}>
          MAKO Renderer reads Lossless.dll from your Lossless Scaling installation. The default
          branch and the lsfg-vk branch both include it, but the selected branch does not.
        </div>
        <ol style={{ lineHeight: 1.5, margin: "14px 0 18px", paddingLeft: "24px" }}>
          <li>Open Lossless Scaling in your Steam library.</li>
          <li>Open Properties, then Game Versions &amp; Betas.</li>
          <li>Select <strong>None</strong> (the default public branch).</li>
          <li>Wait for Steam to finish the update and reopen Jedi LSFG-VK.</li>
        </ol>
        <DialogButton
          onClick={() => closeModal()}
          style={{ width: "100%" }}
        >
          Close
        </DialogButton>
      </div>
    </ModalRoot>,
    undefined,
    {
      strTitle: "Finish Jedi LSFG-VK setup",
      bNeverPopOut: true,
      popupWidth: 980,
      popupHeight: 760,
    },
  );
  closeModal = modal.Close;
}
