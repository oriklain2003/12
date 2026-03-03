/**
 * Inline parameter editor for a single CubeNode input param.
 * Hides when a connection provides the value, showing "Connected" instead.
 */

import { TagsInput } from 'react-tag-input-component';
import { ParamType } from '../../types/cube';
import type { ParamDefinition } from '../../types/cube';
import { useFlowStore } from '../../store/flowStore';
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
          <span className="param-field__connected-icon">⌁</span>
          Connected
        </div>
      </div>
    );
  }

  const renderInput = () => {
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
          <input
            type="checkbox"
            className="nodrag nowheel"
            checked={(currentValue as boolean) ?? false}
            onChange={(e) => updateParam(e.target.checked)}
          />
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
