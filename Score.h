#ifndef SCORE_H
#define SCORE_H

#include "DxLib.h"

class Score {
private:
    int playerScore; // �v���C���[�̃X�R�A
    int cpuScore;    // CPU�̃X�R�A
    const int winScore = 11; // ���������̃X�R�A

public:
    // �R���X�g���N�^
    Score();

    // �X�R�A�̍X�V
    void AddPlayerScore();
    void AddCpuScore();

    // �X�R�A�̕`��
    void Draw() const;

    // �Q�[���I�������̔���
    bool IsGameOver() const;

    // �X�R�A�����Z�b�g
    void Reset();
};

#endif // SCORE_H
