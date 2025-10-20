declare namespace JSX {
  type Element = any;
  interface ElementClass {}
  interface ElementAttributesProperty {
    props: any;
  }
  interface IntrinsicElements {
    [elemName: string]: any;
  }
}
