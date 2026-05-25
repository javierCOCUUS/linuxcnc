declare global {
  namespace JSX {
    interface IntrinsicElements {
      webview: React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement> & {
          src?: string
          preload?: string
          nodeintegration?: string
          disablewebsecurity?: string
          allowpopups?: string
        },
        HTMLElement
      >
    }
  }
}

export {}
