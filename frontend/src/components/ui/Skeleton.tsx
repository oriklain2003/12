import './Skeleton.css';

interface SkeletonProps {
  width?: number | string;
  height?: number | string;
  borderRadius?: number | string;
}

export function Skeleton({ width, height, borderRadius }: SkeletonProps) {
  return (
    <div
      className="skeleton"
      style={{
        width: width ?? '100%',
        height: height ?? 16,
        borderRadius: borderRadius ?? 6,
      }}
    />
  );
}
