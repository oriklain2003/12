/**
 * Inline parameter editor for a single CubeNode input param.
 * Hides when a connection provides the value, showing "Connected" instead.
 */

import { TagsInput } from 'react-tag-input-component';
import { ParamType } from '../../types/cube';
import type { ParamDefinition } from '../../types/cube';
import { useFlowStore } from '../../store/flowStore';
import { RelativeTimeInput } from './RelativeTimeInput';
import { DateTimeInput } from './DateTimeInput';
import { PolygonField } from './PolygonMapWidget';
import './ParamField.css';

interface ParamFieldProps {
  nodeId: string;
  param: ParamDefinition;
}

export function ParamField({ nodeId, param }: ParamFieldProps) {
  // Derive connected state from the store
  const isConnected = useFlowStore(
    (s) => s.edges.some((e) => e.target === nodeId && e.targetHandle === param.name)
  );

  const currentValue = useFlowStore(
    (s) => s.nodes.find((n) => n.id === nodeId)?.data.params[param.name]
  );

  const updateParam = (value: unknown) => {
    useFlowStore.getState().updateNodeParam(nodeId, param.name, value);
  };

  if (isConnected) {
    return (
      <div className="param-field">
        <div className="param-field__connected">
          <svg className="param-field__connected-icon" width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M5 2.5a2.5 2.5 0 0 0 0 5h.5m1.5-5a2.5 2.5 0 0 1 0 5H6.5M4 5h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
          Connected
        </div>
      </div>
    );
  }

  const renderInput = () => {
    // Widget hint takes priority over generic type-based editors
    if (param.widget_hint === 'relative_time') {
      return (
        <RelativeTimeInput
          value={currentValue as number | undefined}
          onChange={updateParam}
          placeholder={param.description}
        />
      );
    }
    if (param.widget_hint === 'datetime') {
      return (
        <DateTimeInput
          value={currentValue as string | undefined}
          onChange={updateParam}
          placeholder={param.description}
        />
      );
    }
    if (param.widget_hint === 'polygon') {
      return (
        <PolygonField
          value={currentValue as number[][] | undefined}
          onChange={updateParam}
        />
      );
    }

    switch (param.type) {
      case ParamType.STRING:
        return (
          <input
            type="text"
            className="nodrag nowheel"
            placeholder={param.description}
            value={(currentValue as string) ?? ''}
            onChange={(e) => updateParam(e.target.value)}
          />
        );

      case ParamType.NUMBER:
        return (
          <input
            type="number"
            className="nodrag nowheel"
            placeholder={param.description}
            value={(currentValue as number) ?? ''}
            onChange={(e) => updateParam(e.target.valueAsNumber)}
          />
        );

      case ParamType.BOOLEAN:
        return (
          <label className="param-toggle nodrag nowheel">
            <input
              type="checkbox"
              checked={(currentValue as boolean) ?? false}
              onChange={(e) => updateParam(e.target.checked)}
            />
            <span className="param-toggle__track">
              <span className="param-toggle__knob" />
            </span>
          </label>
        );

      case ParamType.LIST_OF_STRINGS:
        return (
          <div className="nodrag nowheel">
            <TagsInput
              value={(currentValue as string[]) ?? []}
              onChange={(tags) => updateParam(tags)}
              placeHolder={param.description}
            />
          </div>
        );

      case ParamType.LIST_OF_NUMBERS:
        return (
          <div className="nodrag nowheel">
            <TagsInput
              value={((currentValue as number[]) ?? []).map(String)}
              onChange={(tags) => updateParam(tags.map(Number))}
              placeHolder={param.description}
            />
          </div>
        );

      case ParamType.JSON_OBJECT:
        return (
          <textarea
            className="nodrag nowheel"
            rows={2}
            placeholder={param.description}
            value={(currentValue as string) ?? ''}
            onChange={(e) => updateParam(e.target.value)}
          />
        );

      default:
        return null;
    }
  };

  return (
    <div className="param-field">
      {renderInput()}
    </div>
  );
}
