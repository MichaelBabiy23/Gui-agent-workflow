import React, { memo, useEffect, useMemo, useState } from "react";
import { BaseEdge, getSmoothStepPath, useReactFlow } from "@xyflow/react";

function closestSegment(points, click) {
  let best = 0;
  let distance = Infinity;
  for (let index = 0; index < points.length - 1; index += 1) {
    const start = points[index];
    const end = points[index + 1];
    const dx = end[0] - start[0];
    const dy = end[1] - start[1];
    const fraction = Math.max(
      0,
      Math.min(
        1,
        ((click[0] - start[0]) * dx + (click[1] - start[1]) * dy) /
          (dx * dx + dy * dy || 1),
      ),
    );
    const x = start[0] + fraction * dx;
    const y = start[1] + fraction * dy;
    const current = (x - click[0]) ** 2 + (y - click[1]) ** 2;
    if (current < distance) {
      distance = current;
      best = index;
    }
  }
  return best;
}

function WorkflowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  selected,
  markerEnd,
  data,
}) {
  const rf = useReactFlow();
  const [vertices, setVertices] = useState(data.connection.vertices || []);
  const [dragging, setDragging] = useState(-1);
  useEffect(() => {
    if (dragging < 0) setVertices(data.connection.vertices || []);
  }, [data.connection.vertices, dragging]);
  useEffect(() => {
    if (dragging < 0) return undefined;
    const move = (event) => {
      const position = rf.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });
      setVertices((current) =>
        current.map((point, index) =>
          index === dragging ? [position.x, position.y] : point,
        ),
      );
    };
    const end = (event) => {
      const position = rf.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });
      setVertices((current) => {
        const updated = current.map((point, index) =>
          index === dragging ? [position.x, position.y] : point,
        );
        data.onVertices(updated);
        return updated;
      });
      setDragging(-1);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end, { once: true });
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
    };
  }, [dragging, rf, data]);
  const smooth = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  })[0];
  const path = useMemo(
    () =>
      vertices.length
        ? `M ${sourceX} ${sourceY} ${vertices.map(([x, y]) => `L ${x} ${y}`).join(" ")} L ${targetX} ${targetY}`
        : smooth,
    [vertices, sourceX, sourceY, targetX, targetY, smooth],
  );
  const insert = (event) => {
    event.stopPropagation();
    const point = rf.screenToFlowPosition({
      x: event.clientX,
      y: event.clientY,
    });
    const points = [[sourceX, sourceY], ...vertices, [targetX, targetY]];
    const segment = closestSegment(points, [point.x, point.y]);
    const updated = [...vertices];
    updated.splice(segment, 0, [point.x, point.y]);
    setVertices(updated);
    data.onVertices(updated);
  };
  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        style={{
          stroke: selected ? "#9bb6ff" : "#71809c",
          strokeWidth: selected ? 2.8 : 2,
        }}
      />
      <path
        d={path}
        fill="none"
        stroke="transparent"
        strokeWidth={18}
        onClick={(event) => {
          event.stopPropagation();
          data.onSelect();
        }}
        onDoubleClick={insert}
        style={{ pointerEvents: "stroke", cursor: "crosshair" }}
      />
      {selected &&
        vertices.map(([x, y], index) => (
          <circle
            key={index}
            cx={x}
            cy={y}
            r={7}
            fill="#223c63"
            stroke="#b4cbff"
            strokeWidth={2}
            style={{ cursor: "grab", pointerEvents: "all" }}
            onPointerDown={(event) => {
              event.stopPropagation();
              if (event.shiftKey) {
                const updated = vertices.filter((_, at) => at !== index);
                setVertices(updated);
                data.onVertices(updated);
              } else setDragging(index);
            }}
          />
        ))}
    </>
  );
}

export default memo(WorkflowEdge);
