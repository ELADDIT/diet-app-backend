declare module 'react' {
  export type ReactNode = any;
  export interface DependencyList extends ReadonlyArray<unknown> {}
  export interface FunctionComponent<P = {}> {
    (props: P & { children?: ReactNode }): ReactNode;
  }
  export type FC<P = {}> = FunctionComponent<P>;
  export function useMemo<T>(factory: () => T, deps: DependencyList | undefined): T;
  const React: {
    useMemo: typeof useMemo;
  };
  export default React;
}
