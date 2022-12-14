import sys

sys.path.append('../')
from dataset import LetorDataset
import numpy as np
from clickModel.PBM import PBM
from ranker.ActorCriticLinearRanker import ActorCriticLinearRanker
# from ranker.ActorCriticLinearRankerV2 import ActorCriticLinearRankerV2
from utils import evl_tool
from utils.utility import get_DCG_rewards, get_DCG_MDPrewards
import multiprocessing as mp
import pickle


# %%
def run(train_set, test_set, ranker, eta, reward_method, num_interation, click_model):
    ndcg_scores = []
    cndcg_scores = []
    query_set = train_set.get_all_querys()
    index = np.random.randint(query_set.shape[0], size=num_interation)
    num_iter = 0
    for i in index:
        qid = query_set[i]
        result_list = ranker.get_query_result_list(train_set, qid)
        clicked_doces, click_labels, _ = click_model.simulate(qid, result_list, train_set)

        if len(clicked_doces) == 0:
            if num_iter % 1000 == 0:
                all_result = ranker.get_all_query_result_list(test_set)
                ndcg = evl_tool.average_ndcg_at_k(test_set, all_result, 10)
                ndcg_scores.append(ndcg)

            cndcg = evl_tool.query_ndcg_at_k(train_set, result_list, qid, 10)
            cndcg_scores.append(cndcg)
            num_iter += 1
            # print(num_iter, ndcg)
            continue

        propensities = np.power(np.divide(1, np.arange(1.0, len(result_list) + 1)), eta)

        # directly using pointwise rewards
        rewards = get_DCG_rewards(click_labels, propensities, reward_method)
        # using listwise rewards

        # rewards = get_DCG_MDPrewards(click_labels, propensities, reward_method, gamma=0.99)

        # ranker.record_episode(qid, result_list, rewards)

        ranker.update_actor_critic(qid, result_list, rewards, train_set)

        # if num_iter % 1000 == 0:
        all_result = ranker.get_all_query_result_list(test_set)
        ndcg = evl_tool.average_ndcg_at_k(test_set, all_result, 10)
        ndcg_scores.append(ndcg)
        print(num_iter, ndcg)
        cndcg = evl_tool.query_ndcg_at_k(train_set, result_list, qid, 10)
        cndcg_scores.append(cndcg)

        num_iter += 1
    return ndcg_scores, cndcg_scores


def job(model_type, learning_rate, eta, reward_method, f, train_set, test_set, num_features, output_fold):
    if model_type == "perfect":
        pc = [0.0, 0.5, 1.0]
        ps = [0.0, 0.0, 0.0]
    elif model_type == "navigational":
        pc = [0.05, 0.5, 0.95]
        ps = [0.2, 0.5, 0.9]
    elif model_type == "informational":
        pc = [0.4, 0.7, 0.9]
        ps = [0.1, 0.3, 0.5]

    cm = PBM(pc, 1)

    for r in range(1, 16):
        # np.random.seed(r)
        # ranker = ActorCriticLinearRankerV2(num_features, learning_rate, 256)
        ranker = ActorCriticLinearRanker(num_features, learning_rate, 256)
        print("ActorCritic mq2007 fold{} {} eta{} reward{} run{} start!".format(f, model_type, eta, reward_method, r))
        ndcg_scores, cndcg_scores = run(train_set, test_set, ranker, eta, reward_method, NUM_INTERACTION, cm)
        # with open(
        #         "{}/fold{}/{}_run{}_ndcg.txt".format(output_fold, f, model_type, r),
        #         "wb") as fp:
        #     pickle.dump(ndcg_scores, fp)
        # with open(
        #         "{}/fold{}/{}_run{}_cndcg.txt".format(output_fold, f, model_type, r),
        #         "wb") as fp:
        #     pickle.dump(cndcg_scores, fp)


if __name__ == "__main__":

    FEATURE_SIZE = 46
    NUM_INTERACTION = 100000
    learning_rate = 0.001
    eta = 1
    reward_method = "both"

    # click_models = ["informational", "perfect"]
    click_models = ["informational"]
    dataset_fold = "../datasets/2007_mq_dataset"
    output_fold = "results/mq2007/AC_003_both"

    # for 5 folds
    for f in range(1, 2):
        training_path = "{}/Fold{}/train.txt".format(dataset_fold, f)
        test_path = "{}/Fold{}/test.txt".format(dataset_fold, f)
        train_set = LetorDataset(training_path, FEATURE_SIZE, query_level_norm=True)
        test_set = LetorDataset(test_path, FEATURE_SIZE, query_level_norm=True)
        # %%
        processors = []
        # for 3 click_models
        for click_model in click_models:
            p = mp.Process(target=job, args=(click_model, learning_rate, eta, reward_method, f, train_set, test_set, FEATURE_SIZE, output_fold))
            p.start()
            processors.append(p)
    for p in processors:
        p.join()
