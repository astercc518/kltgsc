import React from 'react';
import { Modal, Button, List, Checkbox, message, Spin, Typography } from 'antd';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { groupAiApi, CaseStudyExtractedCandidate } from '../../api/groupAi';

const { Paragraph } = Typography;

export default function CaseExtractModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [candidates, setCandidates] = React.useState<CaseStudyExtractedCandidate[]>([]);
  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const qc = useQueryClient();

  const extractMut = useMutation({
    mutationFn: () => groupAiApi.extractCases(100),
    onSuccess: (data) => setCandidates(data.candidates),
  });
  const batchMut = useMutation({
    mutationFn: () => {
      const items = candidates.filter((_, i) => selected.has(i));
      return groupAiApi.batchCreateCases(items);
    },
    onSuccess: () => {
      message.success(`已录入 ${selected.size} 条`);
      qc.invalidateQueries({ queryKey: ['portal-cases'] });
      setSelected(new Set());
      setCandidates([]);
      onClose();
    },
  });

  React.useEffect(() => {
    if (open && candidates.length === 0) extractMut.mutate();
  }, [open]);

  return (
    <Modal title="从主号历史会话扫描案例" open={open} onCancel={onClose} width={800}
           footer={[
             <Button key="cancel" onClick={onClose}>取消</Button>,
             <Button key="save" type="primary"
                     disabled={selected.size === 0}
                     loading={batchMut.isPending}
                     onClick={() => batchMut.mutate()}>
               录入选中 {selected.size} 条
             </Button>,
           ]}>
      {extractMut.isPending ? <Spin tip="AI 扫描中..." /> : (
        <>
          <Paragraph type="secondary">
            勾选要录入的案例。AI 自动从主号历史聊天里识别出的"已完成成交"事件，需要你审一遍。
          </Paragraph>
          <List
            dataSource={candidates}
            renderItem={(item, i) => (
              <List.Item>
                <Checkbox
                  checked={selected.has(i)}
                  onChange={(e) => {
                    const next = new Set(selected);
                    if (e.target.checked) next.add(i); else next.delete(i);
                    setSelected(next);
                  }}
                >
                  <strong>{item.industry || '未填'} | {item.deal_size}</strong> | {item.period}
                  <br />
                  问题: {item.problem}<br />
                  方案: {item.solution}<br />
                  效果: {item.outcome}
                </Checkbox>
              </List.Item>
            )}
          />
        </>
      )}
    </Modal>
  );
}
